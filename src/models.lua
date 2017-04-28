
include 'word2vecLookupTable.lua'

function nn.Module:reuseMem()
	self.reuse = true
	return self
end

function nn.Module:setReuse()
	if self.reuse then
		self.gradInput = self.output
	end
end

function make_encoder(data, opt)
  local x = nn.Identity()()
  local word_vecs = nn.Dropout(opt.enc_dropout)(word2vecLookupTable(data.source_size, opt.word_vec_size, opt.word2vecfile, opt.word2vec_size, opt.word2vec_dim)(x))
  local input_size_L = opt.word_vec_size + opt.word2vec_dim
   local lstm_out = cudnn.BLSTM(input_size_L, opt.rnn_size / 2, opt.num_layers)(word_vecs)
  --local out = nn.CAddTable()({nn.Narrow(3, 1, opt.rnn_size)(lstm_out), nn.Narrow(3, opt.rnn_size + 1, opt.rnn_size)(lstm_out) })
  return nn.gModule({x}, {lstm_out}) 
end 

function make_lstm(data, opt, model, use_chars)
	assert(model == 'enc' or model == 'dec')
	local name = '_' .. model
	local dropout = opt.dropout or 0
	local n = opt.num_layers
	local rnn_size = opt.rnn_size
	local input_size = opt.word_vec_size
	local offset = 0
	-- there will be 2*n+3 inputs
	local inputs = {}
	table.insert(inputs, nn.Identity()()) -- x (batch_size x max_word_l)
	if model == 'dec' then
		table.insert(inputs, nn.Identity()()) -- all context (batch_size x source_l x rnn_size)
		offset = offset + 1
		if opt.input_feed == 1 then
			table.insert(inputs, nn.Identity()()) -- prev context_attn (batch_size x rnn_size)
			offset = offset + 1
		end
	end
	for L = 1,n do
		table.insert(inputs, nn.Identity()()) -- prev_c[L]
		table.insert(inputs, nn.Identity()()) -- prev_h[L]
	end

	local x, input_size_L
	local outputs = {}
	for L = 1,n do
		-- c,h from previous timesteps
		local prev_c = inputs[L*2+offset]    
		local prev_h = inputs[L*2+1+offset]
		-- the input to this layer
		if L == 1 then
			local word_vecs = nn.LookupTable(data.target_size, input_size)
		  x = word_vecs(inputs[1]) -- batch_size x word_vec_size
			word_vecs.name = 'word_vecs' .. name
			input_size_L = input_size
			if opt.input_feed == 1 then
				x = nn.JoinTable(2)({x, inputs[1+offset]}) -- batch_size x (word_vec_size + rnn_size)
				input_size_L = input_size + rnn_size
			end	  
		else
			x = outputs[(L-1)*2]
			if opt.res_net == 1 and L > 2 then
				x = nn.CAddTable()({x, outputs[(L-2)*2]})       
			end       
			input_size_L = rnn_size
			if opt.multi_attn == L and model == 'dec' then
				local multi_attn = make_decoder_attn(data, opt, 1)
				multi_attn.name = 'multi_attn' .. L
				x = multi_attn({x, inputs[2]})
			end
			if dropout > 0 then
				x = nn.Dropout(dropout, nil, false)(x)
			end
		end

			-- evaluate the input sums at once for efficiency
			local i2h = nn.Linear(input_size_L, 4 * rnn_size):reuseMem()(x)
			local h2h = nn.Linear(rnn_size, 4 * rnn_size):reuseMem()(prev_h)
			local all_input_sums = nn.CAddTable()({i2h, h2h})

			local reshaped = nn.Reshape(4, rnn_size)(all_input_sums)
			local n1, n2, n3, n4 = nn.SplitTable(2)(reshaped):split(4)
			-- decode the gates
			local in_gate = nn.Sigmoid():reuseMem()(n1)
			local forget_gate = nn.Sigmoid():reuseMem()(n2)
			local out_gate = nn.Sigmoid():reuseMem()(n3)
			-- decode the write inputs
			local in_transform = nn.Tanh():reuseMem()(n4)
			-- perform the LSTM update
			local next_c           = nn.CAddTable()({
				nn.CMulTable()({forget_gate, prev_c}),
				nn.CMulTable()({in_gate,     in_transform})
			})
			-- gated cells form the output
			local next_h = nn.CMulTable()({out_gate, nn.Tanh():reuseMem()(next_c)})

			table.insert(outputs, next_c)
			table.insert(outputs, next_h)
	end
		local top_h = outputs[#outputs]
		local decoder_out
		if opt.attn == 1 then
			local decoder_attn = make_decoder_attn(data, opt)
			decoder_attn.name = 'decoder_attn'
			decoder_out = decoder_attn({top_h, inputs[2]})
		else
			decoder_out = nn.JoinTable(2)({top_h, inputs[2]})
			decoder_out = nn.Tanh()(nn.Linear(opt.rnn_size*2, opt.rnn_size)(decoder_out))
		end
		local decoder_out, attn_softmax= unpack({decoder_out:split(2)})
		if dropout > 0 then
			decoder_out = nn.Dropout(dropout, nil, false)(decoder_out)
		end
		table.insert(outputs, decoder_out)
		table.insert(outputs, attn_softmax)
	return nn.gModule(inputs, outputs)
end

function make_decoder_attn(data, opt, simple)
	-- 2D tensor target_t (batch_l x rnn_size) and
	-- 3D tensor for context (batch_l x source_l x rnn_size)

	local inputs = {}
	table.insert(inputs, nn.Identity()())
	table.insert(inputs, nn.Identity()())
	local target_t = nn.Linear(opt.rnn_size, opt.rnn_size)(inputs[1])
	local context = inputs[2]
	simple = simple or 0
	-- get attention

	local attn = nn.MM()({context, nn.Replicate(1,3)(target_t)}) -- batch_l x source_l x 1
	attn = nn.Sum(3)(attn) -- batch_l x source_l
	local softmax_attn = nn.SoftMax()
	softmax_attn.name = 'softmax_attn'
	attn = softmax_attn(attn)
	r_attn = nn.Replicate(1,2)(attn) -- batch_l x  1 x source_l

	-- apply attention to context
	local context_combined = nn.MM()({r_attn, context}) -- batch_l x 1 x rnn_size
	context_combined = nn.Sum(2)(context_combined) -- batch_l x rnn_size
	local context_output
	if simple == 0 then
		context_combined = nn.JoinTable(2)({context_combined, inputs[1]}) -- batch_l x rnn_size*2
		context_output = nn.Tanh()(nn.Linear(opt.rnn_size*2, opt.rnn_size)(context_combined))
	else
		context_output = nn.CAddTable()({context_combined,inputs[1]})
	end   
	return nn.gModule(inputs, {context_output, attn})   
end

function make_generator(data, opt)
	local model = nn.Sequential()
	model:add(nn.Linear(opt.rnn_size, data.target_size))
	model:add(nn.LogSoftMax())
	local w = torch.ones(data.target_size)
	w[1] = 0
	criterion = nn.ClassNLLCriterion(w)
	criterion.sizeAverage = false
	return model, criterion
end

function idx2key(file)   
   local f = io.open(file,'r')
   local t = {}
   for line in f:lines() do
      local c = {}
      for w in line:gmatch'([^%s]+)' do
	 table.insert(c, w)
      end
      t[tonumber(c[2])] = c[1]
   end   
   return t
end

function flip_table(u)
   local t = {}
   for key, value in pairs(u) do
      t[value] = key
   end
   return t   
end



