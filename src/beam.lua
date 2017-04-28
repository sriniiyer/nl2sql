require 'nn'
require 'cudnn'
require 'string'
require 'hdf5'
require 'nngraph'

require 'models.lua'
require 'data.lua'
require 'util.lua'

stringx = require('pl.stringx')

cmd = torch.CmdLine()

-- file location
cmd:option('-model', 'seq2seq_lstm_attn.t7.', [[Path to model .t7 file]])
cmd:option('-src_file', '',[[Source sequence to decode (one line per sequence)]])
cmd:option('-training_nl', '',[[for closest match]])
cmd:option('-training_sql', '',[[for closest match]])
cmd:option('-targ_file', '', [[True target sequence (optional)]])
cmd:option('-output_file', 'pred.txt', [[Path to output the predictions (each line will be the
decoded sequence]])
cmd:option('-src_dict', 'data/demo.src.dict', [[Path to source vocabulary (*.src.dict file)]])
cmd:option('-word2vec_dict', 'data/word2vec/word2vec.dict.num', [[Path to source vocabulary (*.src.dict file)]])
cmd:option('-targ_dict', 'data/demo.targ.dict', [[Path to target vocabulary (*.targ.dict file)]])
cmd:option('-char_dict', 'data/demo.char.dict', [[If using chars, path to character 
vocabulary (*.char.dict file)]])

-- beam search options
cmd:option('-beam', 5,[[Beam size]])
cmd:option('-max_sent_l', 250, [[Maximum sentence length. If any sequences in srcfile are longer
than this then it will error out]])
cmd:option('-simple', 0, [[If = 1, output prediction is simply the first time the top of the beam
												 ends with an end-of-sentence token. If = 0, the model considers all 
												 hypotheses that have been generated so far that ends with end-of-sentence 
												 token and takes the highest scoring of all of them.]])
cmd:option('-replace_unk', 0, [[Replace the generated UNK tokens with the source token that 
had the highest attention weight. If srctarg_dict is provided, 
it will lookup the identified source token and give the corresponding 
target token. If it is not provided (or the identified source token
does not exist in the table) then it will copy the source token]])
cmd:option('-srctarg_dict', 'data/en-de.dict', [[Path to source-target dictionary to replace UNK 
tokens. See README.md for the format this file should be in]])
cmd:option('-score_gold', 1, [[If = 1, score the log likelihood of the gold as well]])
cmd:option('-n_best', 1, [[If > 1, it will also output an n_best list of decoded sentences]])
cmd:option('-gpuid',  -1, [[ID of the GPU to use (-1 = use CPU)]])
cmd:option('-gpuid2', -1, [[Second GPU ID]])
cmd:option('-server', 0, [[Should we use server mode]])
cmd:option('-port', 12132, [[port]])
cmd:option('-cudnn', 0, [[If using character model, this should be = 1 if the character model
												 was trained using cudnn]])
opt = cmd:parse(arg)

function copy(orig)
 local orig_type = type(orig)
 local copy
 if orig_type == 'table' then
	 copy = {}
	 for orig_key, orig_value in pairs(orig) do
		 copy[orig_key] = orig_value
	 end
 else
	 copy = orig
 end
 return copy
end

local StateAll = torch.class("StateAll")

function StateAll.initial(start)
 return {start}
end

function StateAll.advance(state, token)
 local new_state = copy(state)
 table.insert(new_state, token)
 return new_state
end

function StateAll.disallow(out)
 local bad = {1, 3} -- 1 is PAD, 3 is BOS
 for j = 1, #bad do
	 out[bad[j]] = -1e9
 end
end

function StateAll.filter_repeats(out, hist, threshold)
 for j = 5, out:size(1) do
	 if hist[j] ~= nil and idx2word_targ[j] ~= nil and #idx2word_targ[j] > threshold then
		 out[j] = -1e9
	 end
 end
end

function StateAll.same(state1, state2)
 for i = 2, #state1 do
	 if state1[i] ~= state2[i] then
		 return false
	 end
 end
 return true
end

function StateAll.next(state)
 return state[#state]
end

function StateAll.heuristic(state)
 return 0
end

function StateAll.print(state)
 for i = 1, #state do
	 io.write(state[i] .. " ")
 end
 print()
end


-- Convert a flat index to a row-column tuple.
function flat_to_rc(v, flat_index)
 local row = math.floor((flat_index - 1) / v:size(2)) + 1
 return row, (flat_index - 1) % v:size(2) + 1
end

function generate_beam(model, initial, K, max_sent_l, source, source_g, gold)
 --reset decoder initial states
 if opt.gpuid >= 0 and opt.gpuid2 >= 0 then
	 cutorch.setDevice(opt.gpuid)
 end
 local n = max_sent_l
 -- Backpointer table.
 local prev_ks = torch.LongTensor(n, K):fill(1)
 -- Current States.
 local next_ys = torch.LongTensor(n, K):fill(1)
 -- Current Scores.
 local scores = torch.FloatTensor(n, K)
 scores:zero()
 local source_l = math.min(source:size(1), opt.max_sent_l)
 local attn_argmax = {}   -- store attn weights
 attn_argmax[1] = {}

 local states = {} -- store predicted word idx
 states[1] = {}
 for k = 1, 1 do
	 table.insert(states[1], initial)
	 table.insert(attn_argmax[1], initial)
	 next_ys[1][k] = State.next(initial)
 end

 local source_input
 if model_opt.use_chars_enc == 1 then
	 source_input = source:view(source_l, 1, source:size(2)):contiguous()
 else
	 source_input = source:view(source_l, 1)
	 source_word2vec = source_g:view(source_l, 1)
 end

 local rnn_state_enc = {}
 for i = 1, #init_fwd_enc do
	 table.insert(rnn_state_enc, init_fwd_enc[i]:zero())
 end   
 local context = context_proto[{{}, {1,source_l}}]:clone() -- 1 x source_l x rnn_size
 rnn_state_dec = {}
 for i = 1, #init_fwd_dec do
	 table.insert(rnn_state_dec, init_fwd_dec[i]:zero())
 end

 local encoder_input = {source_input, source_word2vec}
 local out = model[1]:forward(encoder_input)
 context[{{},t}]:copy(out:transpose(1, 2))

 if model_opt.init_dec == 1 then
	 for L = 1, model_opt.num_layers do
		 -- copy encoder last hidden state to decoder initial state
		 rnn_state_dec[L*2+model_opt.input_feed]:copy(context[{{},{out:size(1)}, t}]:select(2, 1):expand(K, model_opt.rnn_size ))
	 end
 end	 


 context = context:expand(K, source_l, model_opt.rnn_size)

 out_float = torch.FloatTensor()

 local i = 1
 local done = false
 local max_score = -1e9
 local found_eos = false
 while (not done) and (i < n) do
	 i = i+1
	 states[i] = {}
	 attn_argmax[i] = {}
	 local decoder_input1
	 if model_opt.use_chars_dec == 1 then
		 decoder_input1 = word2charidx_targ:index(1, next_ys:narrow(1,i-1,1):squeeze())
	 else
		 decoder_input1 = next_ys:narrow(1,i-1,1):squeeze()
		 if opt.beam == 1 then
			 decoder_input1 = torch.LongTensor({decoder_input1})
		 end	
	 end
	 local decoder_input
	 if model_opt.attn == 1 then
		 decoder_input = {decoder_input1, context, table.unpack(rnn_state_dec)}
	 else
		 decoder_input = {decoder_input1, context[{{}, source_l}], table.unpack(rnn_state_dec)}
	 end      
	 local out_decoder = model[2]:forward(decoder_input)


	 -- To not break the code, lets separate out the attention
	 local attn_softmax = out_decoder[#out_decoder]
	 out_decoder[#out_decoder] = nil

	 local out = model[3]:forward(out_decoder[#out_decoder]) -- K x vocab_size

	 rnn_state_dec = {} -- to be modified later
	 if model_opt.input_feed == 1 then
		 table.insert(rnn_state_dec, out_decoder[#out_decoder])
	 end      
	 for j = 1, #out_decoder - 1 do
		 table.insert(rnn_state_dec, out_decoder[j])
	 end
	 out_float:resize(out:size()):copy(out)
	 for k = 1, K do
		 State.disallow(out_float:select(1, k))
		 if opt.disallow_repeats ~= nil then
			 State.filter_repeats(out_float:select(1, k), get_words(next_ys, prev_ks, k, i - 1), opt.disallow_repeats)
		 end
		 out_float[k]:add(scores[i-1][k])
	 end
	 -- All the scores available.

	 local flat_out = out_float:view(-1)
	 if i == 2 then
		 flat_out = out_float[1] -- all outputs same for first batch
	 end

	 if model_opt.start_symbol == 1 then
		 decoder_softmax.output[{{},1}]:zero()
		 decoder_softmax.output[{{},source_l}]:zero()
	 end

	 for k = 1, K do
		 while true do
			 local score, index = flat_out:max(1)
			 local score = score[1]
			 local prev_k, y_i = flat_to_rc(out_float, index[1])
			 states[i][k] = State.advance(states[i-1][prev_k], y_i)
			 local diff = true
			 for k2 = 1, k-1 do
				 if State.same(states[i][k2], states[i][k]) then
					 diff = false
				 end
			 end

			 if i < 2 or diff then
				 if model_opt.attn == 1 then
					 max_attn, max_index = decoder_softmax.output[prev_k]:max(1)
					 attn_argmax[i][k] = State.advance(attn_argmax[i-1][prev_k],max_index[1])         
				 end		
				 prev_ks[i][k] = prev_k
				 next_ys[i][k] = y_i
				 scores[i][k] = score
				 flat_out[index[1]] = -1e9
				 break -- move on to next k 
			 end
			 flat_out[index[1]] = -1e9
		 end
	 end
	 for j = 1, #rnn_state_dec do
		 rnn_state_dec[j]:copy(rnn_state_dec[j]:index(1, prev_ks[i]))
	 end
 end_hyp = states[i][1]
end_score = scores[i][1]
if model_opt.attn == 1 then
end_attn_argmax = attn_argmax[i][1]
end       
if end_hyp[#end_hyp] == END then
done = true
found_eos = true
else
for k = 1, K do
local possible_hyp = states[i][k]
if possible_hyp[#possible_hyp] == END then
found_eos = true
if scores[i][k] > max_score then
 max_hyp = possible_hyp
 max_score = scores[i][k]
 if model_opt.attn == 1 then
	 max_attn_argmax = attn_argmax[i][k]
 end		   
end
end	     
end	  
end       
end
local gold_score = 0
if opt.score_gold == 1 then
rnn_state_dec = {}
for i = 1, #init_fwd_dec do
table.insert(rnn_state_dec, init_fwd_dec[i][{{1}}]:zero())
end
if model_opt.init_dec == 1 then
rnn_state_dec = rnn_state_dec_gold
end
local target_l = gold:size(1) 
for t = 2, target_l do
local decoder_input1
if model_opt.use_chars_dec == 1 then
decoder_input1 = word2charidx_targ:index(1, gold[{{t-1}}])
else
decoder_input1 = gold[{{t-1}}]
end
local decoder_input
if model_opt.attn == 1 then
decoder_input = {decoder_input1, context[{{1}}], table.unpack(rnn_state_dec)}
else
decoder_input = {decoder_input1, context[{{1}, source_l}], table.unpack(rnn_state_dec)}
end      	 
local out_decoder = model[2]:forward(decoder_input)
local out = model[3]:forward(out_decoder[#out_decoder]) -- K x vocab_size
rnn_state_dec = {} -- to be modified later
if model_opt.input_feed == 1 then
table.insert(rnn_state_dec, out_decoder[#out_decoder])
end	 
for j = 1, #out_decoder - 1 do
table.insert(rnn_state_dec, out_decoder[j])
end
gold_score = gold_score + out[1][gold[t]]

end      
end
if opt.simple == 1 or end_score > max_score or not found_eos then
max_hyp = end_hyp
max_score = end_score
max_attn_argmax = end_attn_argmax
end

return max_hyp, max_score, max_attn_argmax, gold_score, states[i], scores[i], attn_argmax[i]
end

function get_words(next_ys, prev_ks, k, c_i)
	local words = {}
	for i = c_i, 1, -1 do
		words[next_ys[i][k]] = true
		k = prev_ks[i][k]
	end
	return words
end

function get_layer(layer)
	if layer.name ~= nil then
		if layer.name == 'decoder_attn' then
			decoder_attn = layer
		elseif layer.name:sub(1,3) == 'hop' then
			hop_attn = layer
		elseif layer.name:sub(1,7) == 'softmax' then
			table.insert(softmax_layers, layer)
		elseif layer.name == 'word_vecs_enc' then
			word_vecs_enc = layer
		elseif layer.name == 'word_vecs_dec' then
			word_vecs_dec = layer
		end       
	end
end

function sent2wordidx(sent, word2idx, word2word2vec, start_symbol)
	local t = {}
	local u = {}
	local g = {}
	if start_symbol == 1 then
		table.insert(t, START)
		table.insert(g, START)
		table.insert(u, START_WORD)
	end

	for word in sent:gmatch'([^%s]+)' do
		local idx = word2idx[word] or UNK 
		local glv  = word2word2vec[word] or UNK 
-- 		if idx ~= UNK then
			table.insert(t, idx)
			table.insert(g, glv)
			table.insert(u, word)
-- 		end
	end
	if start_symbol == 1 then
		table.insert(t, END)
		table.insert(g, END)
		table.insert(u, END_WORD)
	end   
	return torch.LongTensor(t), torch.LongTensor(g), u
end

function sent2charidx(sent, char2idx, max_word_l, start_symbol)
local words = {}
if start_symbol == 1 then
table.insert(words, START_WORD)
end   
for word in sent:gmatch'([^%s]+)' do
table.insert(words, word)
end
if start_symbol == 1 then
table.insert(words, END_WORD)
end   
local chars = torch.ones(#words, max_word_l)
for i = 1, #words do
chars[i] = word2charidx(words[i], char2idx, max_word_l, chars[i])
end
return chars, words
end

function word2charidx(word, char2idx, max_word_l, t)
t[1] = START
local i = 2
for _, char in utf8.next, word do
char = utf8.char(char)
local char_idx = char2idx[char] or UNK
t[i] = char_idx
i = i+1
if i >= max_word_l then
t[i] = END
break
end
end
if i < max_word_l then
t[i] = END
end
return t
end

function wordidx2sent(sent, idx2word, source_str, attn, skip_end)
local t = {}
local start_i, end_i
skip_end = skip_start_end or true
if skip_end then
end_i = #sent-1
else
end_i = #sent
end   
for i = 2, end_i do -- skip START and END
if sent[i] == UNK then
if opt.replace_unk == 1 then
local s = source_str[attn[i]]
if phrase_table[s] ~= nil then
--print(s .. ':' ..phrase_table[s])
end	    
local r = phrase_table[s] or s
-- 	    if string.find(r, ' ', 1) ~= nil then
-- 	    	print('srini' .. r)
-- 			end
table.insert(t, r)	    
else
table.insert(t, idx2word[sent[i]])
end	 
else
table.insert(t, idx2word[sent[i]])	 
end           
end
return table.concat(t, ' ')
end

function clean_sent(sent)
	local s = stringx.replace(sent, UNK_WORD, '')
	s = stringx.replace(s, START_WORD, '')
	s = stringx.replace(s, END_WORD, '')
	s = stringx.replace(s, START_CHAR, '')
	s = stringx.replace(s, END_CHAR, '')
  return s
end

function strip(s)
return s:gsub("^%s+",""):gsub("%s+$","")
end

function main()
-- some globals
PAD = 1; UNK = 2; START = 3; END = 4
PAD_WORD = '<blank>'; UNK_WORD = '<unk>'; START_WORD = '<s>'; END_WORD = '</s>'
START_CHAR = '{'; END_CHAR = '}'
MAX_SENT_L = opt.max_sent_l
assert(path.exists(opt.model), 'model does not exist')

-- parse input params
opt = cmd:parse(arg)
if opt.gpuid >= 0 then
	require 'cutorch'
	require 'cunn'
end      
io.stderr:write('loading ' .. opt.model .. '...' .. '\n')
checkpoint = torch.load(opt.model)

if opt.replace_unk == 1 then
	phrase_table = {}
	if path.exists(opt.srctarg_dict) then
		local f = io.open(opt.srctarg_dict,'r')
			for line in f:lines() do
				local c = line:split("|||")
				phrase_table[strip(c[1])] = c[2]
			end
	end
end


-- load model and word2idx/idx2word dictionaries
model, model_opt = checkpoint[1], checkpoint[2]  
for i = 1, #model do
  model[i]:evaluate()
end
-- for backward compatibility
model_opt.brnn = model_opt.brnn or 0
model_opt.input_feed = model_opt.input_feed or 1
model_opt.attn = model_opt.attn or 1

idx2word_src = idx2key(opt.src_dict)
word2vec2word_src = idx2key(opt.word2vec_dict)
word2word2vec_src = flip_table(word2vec2word_src)
word2idx_src = flip_table(idx2word_src)
idx2word_targ = idx2key(opt.targ_dict)
word2idx_targ = flip_table(idx2word_targ)

-- load character dictionaries if needed
if model_opt.use_chars_enc == 1 or model_opt.use_chars_dec == 1 then
	utf8 = require 'lua-utf8'      
	char2idx = flip_table(idx2key(opt.char_dict))
	model[1]:apply(get_layer)
end

if model_opt.use_chars_dec == 1 then
	word2charidx_targ = torch.LongTensor(#idx2word_targ, model_opt.max_word_l):fill(PAD)
	for i = 1, #idx2word_targ do
		word2charidx_targ[i] = word2charidx(idx2word_targ[i], char2idx,
		model_opt.max_word_l, word2charidx_targ[i])
	end      
end  
-- load gold labels if it exists
if path.exists(opt.targ_file) then
	print('loading GOLD labels at ' .. opt.targ_file)
	gold = {}
	local file = io.open(opt.targ_file, 'r')
	for line in file:lines() do
		table.insert(gold, line)
	end
else
	opt.score_gold = 0
end

if opt.gpuid >= 0 then
	cutorch.setDevice(opt.gpuid)
	for i = 1, #model do
		if opt.gpuid2 >= 0 then
			if i == 1 or i == 4 then
				cutorch.setDevice(opt.gpuid)
			else
				cutorch.setDevice(opt.gpuid2)
			end
		end	 	       
		model[i]:double():cuda()
		model[i]:evaluate()
	end
end

softmax_layers = {}
model[2]:apply(get_layer)
if model_opt.attn == 1 then
	decoder_attn:apply(get_layer)
	decoder_softmax = softmax_layers[1]
	attn_layer = torch.zeros(opt.beam, MAX_SENT_L)      
end


context_proto = torch.zeros(1, MAX_SENT_L, model_opt.rnn_size)
local h_init_dec = torch.zeros(opt.beam, model_opt.rnn_size)
local h_init_enc = torch.zeros(1, model_opt.rnn_size) 
if opt.gpuid >= 0 then
	h_init_enc = h_init_enc:cuda()      
	h_init_dec = h_init_dec:cuda()
	cutorch.setDevice(opt.gpuid)
	if opt.gpuid2 >= 0 then
		cutorch.setDevice(opt.gpuid)
		context_proto = context_proto:cuda()	 
		cutorch.setDevice(opt.gpuid2)
		context_proto2 = torch.zeros(opt.beam, MAX_SENT_L, model_opt.rnn_size):cuda()
	else
		context_proto = context_proto:cuda()
	end
	if model_opt.attn == 1 then
		attn_layer = attn_layer:cuda()
	end      
end
init_fwd_enc = {}
init_fwd_dec = {} -- initial context
if model_opt.input_feed == 1 then
	table.insert(init_fwd_dec, h_init_dec:clone())
end

for L = 1, model_opt.num_layers do
	table.insert(init_fwd_enc, h_init_enc:clone())
	table.insert(init_fwd_enc, h_init_enc:clone())
	table.insert(init_fwd_dec, h_init_dec:clone()) -- memory cell
	table.insert(init_fwd_dec, h_init_dec:clone()) -- hidden state      
end      

pred_score_total = 0
gold_score_total = 0
pred_words_total = 0
gold_words_total = 0

State = StateAll
local sent_id = 0
pred_sents = {}

function load_training_file(nlname, fname)
	train_set = {}
  local fsql  = io.open(fname, "r")
  local fnl = io.open(nlname, "r")
	while true do
        sql = fsql:read()
        nl = fnl:read()
        if sql == nil then break end
        train_set[sql:gsub("%s+", "")] = nl
  end
end

function pred_sent(line)
	local line = clean_sent(line)
	local source, source_g, source_str = sent2wordidx(line, word2idx_src, word2word2vec_src, model_opt.start_symbol)
	local state = State.initial(START)
	local pred, pred_score, attn, gold_score, all_sents, all_scores, all_attn = generate_beam(model, state, opt.beam, MAX_SENT_L, source, source_g, target)
	local pred_sent = wordidx2sent(pred, idx2word_targ, source_str, attn, true)
	return pred, pred_score, attn, pred_sent
end

if opt.server == 1 then

	load_training_file(opt.training_nl, opt.training_sql)
	require "socket"
	server = assert(socket.bind("*", opt.port))
	server_state = "running"
	ip, port = server:getsockname()

	while server_state == "running" do
		print("wait for connection on port: " .. opt.port)
		local client = server:accept()
		nl, err = client:receive()
		print(nl)
		local pred, pred_score, attn, pred_sent = pred_sent(nl)
		local without_spaces = pred_sent:gsub("%s+", "")
		local nearest
		if train_set[without_spaces] ~= nil then
      nearest = train_set[without_spaces]
    else
      nearest = "novel"
		end
		client:send(pred_sent .. '\t' .. nearest .. '\n')
		client:close()
  end


end


assert(path.exists(opt.src_file), 'src_file does not exist')
local file = io.open(opt.src_file, "r")
local out_file = io.open(opt.output_file,'w')
file_size = 0
for _ in io.lines(opt.src_file) do
	file_size = file_size + 1
end

for line in file:lines() do
	sent_id = sent_id + 1
	local pred, pred_score, attn, pred_sent = pred_sent(line)
	--xlua.progress(sent_id, file_size)
	-- print('SENT ' .. sent_id .. ': ' ..line)
	pred_score_total = pred_score_total + pred_score
	pred_words_total = pred_words_total + #pred - 1
	out_file:write(pred_sent .. '\n')      
	-- print('PRED ' .. sent_id .. ': ' .. pred_sent)
-- print('')
end
-- print(string.format("PRED AVG SCORE: %.4f, PRED PPL: %.4f", pred_score_total / pred_words_total,
--	       math.exp(-pred_score_total/pred_words_total)))
if opt.score_gold == 1 then      
-- print(string.format("GOLD AVG SCORE: %.4f, GOLD PPL: %.4f",
-- 			  gold_score_total / gold_words_total,
-- 			  math.exp(-gold_score_total/gold_words_total)))
end
out_file:close()

end
main()

