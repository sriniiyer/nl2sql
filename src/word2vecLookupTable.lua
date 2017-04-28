local word2vecLookupTable, parent = torch.class('word2vecLookupTable', 'nn.LookupTable')

function word2vecLookupTable:__init(nIndex, nOutput, word2vecFile, word2vecSize, word2vecDim)
   parent.__init(self, nIndex, nOutput)
   self.nOutput = nOutput
   self.word2vecDim = word2vecDim

	 if self.word2vecDim > 0 then
		 self.word2vec = torch.CudaTensor(word2vecSize, word2vecDim):zero()
		 self.output_word2vec = torch.CudaTensor()

		 local ctr = 5
		 for line in io.lines(word2vecFile) do 
			 v = line:split("\t")
			 for i = 1, word2vecDim do
				 self.word2vec[ctr][i] = (v[i + 1] + 0)
			 end
			 ctr = ctr + 1
		 end
	 end

	 self:reset()
end

function word2vecLookupTable:updateOutput(input)
 	word2vecInput = torch.LongTensor():resize(input[2]:size()):copy(input[2])
 	input = input[1]
 	parent.updateOutput(self, input)

	if self.word2vecDim > 0 then
		if input:dim() == 1 then
				 self.output_word2vec:index(self.word2vec, 1, word2vecInput)
		elseif input:dim() == 2 then
				 self.output_word2vec:index(self.word2vec, 1, word2vecInput:view(-1))
				 self.output_word2vec = self.output_word2vec:view(word2vecInput:size(1), word2vecInput:size(2), self.word2vec:size(2))
		else
			 error("input must be a vector or matrix")
		end
		return torch.cat(self.output, self.output_word2vec)
	else
		return self.output
	end
end

function word2vecLookupTable:updateGradInput(input, gradOutput)
   input = input[1]
   dim = #gradOutput:size()
   embGradOutput = gradOutput:narrow(dim, 1, self.nOutput)
   word2vecGradOutput = gradOutput:narrow(dim, self.nOutput + 1, gradOutput:size(dim) - self.nOutput)
   return {parent.updateGradInput(self, input, embGradOutput), word2vecGradOutput}
end

function word2vecLookupTable:accGradParameters(input, gradOutput, scale)
   input = input[1]
   dim = #gradOutput:size()
   gradOutput = gradOutput:narrow(dim, 1, self.nOutput)
   parent.accGradParameters(self, input, gradOutput, scale)
end

function word2vecLookupTable:type(type, tensorCache)
   parent.type(self, type, tensorCache)


   return self
end
