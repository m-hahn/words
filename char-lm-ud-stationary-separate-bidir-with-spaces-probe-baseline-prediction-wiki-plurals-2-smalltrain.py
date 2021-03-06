from paths import WIKIPEDIA_HOME
from paths import CHAR_VOCAB_HOME
from paths import MODELS_HOME

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--language", dest="language", type=str)
parser.add_argument("--load-from", dest="load_from", type=str)
#parser.add_argument("--load-from-baseline", dest="load_from_baseline", type=str)

#parser.add_argument("--save-to", dest="save_to", type=str)

import random

parser.add_argument("--batchSize", type=int, default=16)
parser.add_argument("--char_embedding_size", type=int, default=100)
parser.add_argument("--hidden_dim", type=int, default=1024)
parser.add_argument("--layer_num", type=int, default=1)
parser.add_argument("--weight_dropout_in", type=float, default=0.01)
parser.add_argument("--weight_dropout_hidden", type=float, default=0.1)
parser.add_argument("--char_dropout_prob", type=float, default=0.33)
parser.add_argument("--char_noise_prob", type = float, default= 0.01)
parser.add_argument("--learning_rate", type = float, default= 0.1)
parser.add_argument("--myID", type=int, default=random.randint(0,1000000000))
parser.add_argument("--sequence_length", type=int, default=50)


args=parser.parse_args()
print(args)





import corpusIteratorWiki


def plusL(its):
  for it in its:
       for x in it:
           yield x

def plus(it1, it2):
   for x in it1:
      yield x
   for x in it2:
      yield x

try:
   with open(CHAR_VOCAB_HOME+"/char-vocab-wiki-"+args.language, "r") as inFile:
     itos = inFile.read().strip().split("\n")
except FileNotFoundError:
    print("Creating new vocab")
    char_counts = {}
    # get symbol vocabulary

    with open(WIKIPEDIA_HOME+"/"+args.language+"-vocab.txt", "r") as inFile:
      words = inFile.read().strip().split("\n")
      for word in words:
         for char in word.lower():
            char_counts[char] = char_counts.get(char, 0) + 1
    char_counts = [(x,y) for x, y in char_counts.items()]
    itos = [x for x,y in sorted(char_counts, key=lambda z:(z[0],-z[1])) if y > 50]
    with open(CHAR_VOCAB_HOME+"/char-vocab-wiki-"+args.language, "w") as outFile:
       print("\n".join(itos), file=outFile)
#itos = sorted(itos)
print(itos)
stoi = dict([(itos[i],i) for i in range(len(itos))])




import random


import torch

print(torch.__version__)

from weight_drop import WeightDrop


rnn = torch.nn.LSTM(args.char_embedding_size, args.hidden_dim, args.layer_num).cuda()

rnn_parameter_names = [name for name, _ in rnn.named_parameters()]
print(rnn_parameter_names)
#quit()


rnn_drop = WeightDrop(rnn, [(name, args.weight_dropout_in) for name, _ in rnn.named_parameters() if name.startswith("weight_ih_")] + [ (name, args.weight_dropout_hidden) for name, _ in rnn.named_parameters() if name.startswith("weight_hh_")])

output = torch.nn.Linear(args.hidden_dim, len(itos)+3).cuda()

char_embeddings = torch.nn.Embedding(num_embeddings=len(itos)+3, embedding_dim=args.char_embedding_size).cuda()

logsoftmax = torch.nn.LogSoftmax(dim=2)

train_loss = torch.nn.NLLLoss(ignore_index=0)
print_loss = torch.nn.NLLLoss(size_average=False, reduce=False, ignore_index=0)
char_dropout = torch.nn.Dropout2d(p=args.char_dropout_prob)

modules = [rnn, output, char_embeddings]
def parameters():
   for module in modules:
       for param in module.parameters():
            yield param

optim = torch.optim.SGD(parameters(), lr=args.learning_rate, momentum=0.0) # 0.02, 0.9

named_modules = {"rnn" : rnn, "output" : output, "char_embeddings" : char_embeddings} #, "optim" : optim}

print("Loading model")
if args.load_from is not None:
  checkpoint = torch.load(MODELS_HOME+"/"+args.load_from+".pth.tar")
  for name, module in named_modules.items():
      print(checkpoint[name].keys())
      module.load_state_dict(checkpoint[name])
else:
   assert False
####################################





from torch.autograd import Variable


# ([0] + [stoi[training_data[x]]+1 for x in range(b, b+sequence_length) if x < len(training_data)]) 

#from embed_regularize import embedded_dropout

def encodeWord(word):
      numeric = [[]]
      for char in word:
           numeric[-1].append((stoi[char]+3 if char in stoi else 2) if True else 2+random.randint(0, len(itos)))
      return numeric



rnn_drop.train(False)
#rnn_forward_drop.train(False)
#rnn_backward_drop.train(False)

#baseline_rnn_encoder_drop.train(False)

lossModule = torch.nn.NLLLoss(size_average=False, reduce=False, ignore_index=0)


def choice(numeric1, numeric2):
     assert len(numeric1) == 1
     assert len(numeric2) == 1
     numeric = [numeric1[0], numeric2[0]]
     maxLength = max([len(x) for x in numeric])
     for i in range(len(numeric)):
        while len(numeric[i]) < maxLength:
              numeric[i].append(0)
     input_tensor_forward = Variable(torch.LongTensor([[0]+x for x in numeric]).transpose(0,1).cuda(), requires_grad=False)
     
     target = input_tensor_forward[1:]
     input_cut = input_tensor_forward[:-1]
     embedded_forward = char_embeddings(input_cut)
     out_forward, hidden_forward = rnn_drop(embedded_forward, None)

     prediction = logsoftmax(output(out_forward)) #.data.cpu().view(-1, 3+len(itos)).numpy() #.view(1,1,-1))).view(3+len(itos)).data.cpu().numpy()
     losses = lossModule(prediction.view(-1, len(itos)+3), target.view(-1)).view(maxLength, 2)
     losses = losses.sum(0).data.cpu().numpy()
     return losses


def encodeListOfWords(words):
    numeric = [encodeWord(word)[0] for word in words]
    maxLength = max([len(x) for x in numeric])
    for i in range(len(numeric)):
       numeric[i] = ([0]*(maxLength-len(numeric[i]))) + numeric[i]
    input_tensor_forward = Variable(torch.LongTensor([[0]+x for x in numeric]).transpose(0,1).cuda(), requires_grad=False)
    
    target = input_tensor_forward[1:]
    input_cut = input_tensor_forward[:-1]
    embedded_forward = char_embeddings(input_cut)
    out_forward, hidden_forward = rnn_drop(embedded_forward, None)
    hidden = hidden_forward[0].data.cpu().numpy()
    return [hidden[0][i] for i in range(len(words))]




def choiceList(numeric):
     for x in numeric:
       assert len(x) == 1
#     assert len(numeric1) == 1
 #    assert len(numeric2) == 1
     numeric = [x[0] for x in numeric] #, numeric2[0]]
     maxLength = max([len(x) for x in numeric])
     for i in range(len(numeric)):
        while len(numeric[i]) < maxLength:
              numeric[i].append(0)
     input_tensor_forward = Variable(torch.LongTensor([[0]+x for x in numeric]).transpose(0,1).cuda(), requires_grad=False)
     
     target = input_tensor_forward[1:]
     input_cut = input_tensor_forward[:-1]
     embedded_forward = char_embeddings(input_cut)
     out_forward, hidden_forward = rnn_drop(embedded_forward, None)

     prediction = logsoftmax(output(out_forward)) #.data.cpu().view(-1, 3+len(itos)).numpy() #.view(1,1,-1))).view(3+len(itos)).data.cpu().numpy()
     losses = lossModule(prediction.view(-1, len(itos)+3), target.view(-1)).view(maxLength, len(numeric))
     losses = losses.sum(0).data.cpu().numpy()
     return losses



def encodeSequenceBatchForward(numeric):
      input_tensor_forward = Variable(torch.LongTensor([[0]+x for x in numeric]).transpose(0,1).cuda(), requires_grad=False)

#      target_tensor_forward = Variable(torch.LongTensor(numeric).transpose(0,1)[2:].cuda(), requires_grad=False).view(args.sequence_length+1, len(numeric), 1, 1)
      embedded_forward = char_embeddings(input_tensor_forward)
      out_forward, hidden_forward = rnn_drop(embedded_forward, None)
#      out_forward = out_forward.view(args.sequence_length+1, len(numeric), -1)
 #     logits_forward = output(out_forward) 
  #    log_probs_forward = logsoftmax(logits_forward)
      return (out_forward[-1], hidden_forward)



def encodeSequenceBatchBackward(numeric):
#      print([itos[x-3] for x in numeric[0]])
#      print([[0]+(x[::-1]) for x in numeric])
      input_tensor_backward = Variable(torch.LongTensor([[0]+(x[::-1]) for x in numeric]).transpose(0,1).cuda(), requires_grad=False)
#      target_tensor_backward = Variable(torch.LongTensor([x[::-1] for x in numeric]).transpose(0,1)[:-2].cuda(), requires_grad=False).view(args.sequence_length+1, len(numeric), 1, 1)
      embedded_backward = char_embeddings(input_tensor_backward)
      out_backward, hidden_backward = rnn_backward_drop(embedded_backward, None)
#      out_backward = out_backward.view(args.sequence_length+1, len(numeric), -1)
#      logits_backward = output(out_backward) 
#      log_probs_backward = logsoftmax(logits_backward)

      return (out_backward[-1], hidden_backward)


import numpy as np

def predictNext(encoded, preventBoundary=True):
     out, hidden = encoded
     prediction = logsoftmax(output(out.unsqueeze(0))).data.cpu().view(3+len(itos)).numpy() #.view(1,1,-1))).view(3+len(itos)).data.cpu().numpy()
     predicted = np.argmax(prediction[:-1] if preventBoundary else prediction)
     return itos[predicted-3] #, prediction

def keepGenerating(encoded, length=100, backwards=False):
    out, hidden = encoded
    output_string = ""
   
#    rnn_forward_drop.train(True)

    for _ in range(length):
      prediction = logsoftmax(2*output(out.unsqueeze(0))).data.cpu().view(3+len(itos)).numpy() #.view(1,1,-1))).view(3+len(itos)).data.cpu().numpy()
#      predicted = np.argmax(prediction).items()
      predicted = np.random.choice(3+len(itos), p=np.exp(prediction))

      output_string += itos[predicted-3]

      input_tensor_forward = Variable(torch.LongTensor([[predicted]]).transpose(0,1).cuda(), requires_grad=False)

      embedded_forward = char_embeddings(input_tensor_forward)
      
      out, hidden = (rnn_drop if not backwards else rnn_backward_drop)(embedded_forward, hidden)
      out = out[-1]

 #   rnn_forward_drop.train(False)


    return output_string if not backwards else output_string[::-1]




from corpusIterator import CorpusIterator


plurals = set()

training = CorpusIterator("German", partition="train", storeMorph=True, removePunctuation=True)

for sentence in training.iterator():
 for line in sentence:
   if line["posUni"] == "NOUN":
      morph = line["morph"]
      if "Number=Plur" in  morph and "Case=Dat" not in morph:
        if "|" not in line["lemma"] and line["lemma"].lower() != line["word"]:
          plurals.add((line["lemma"].lower(), line["word"]))

formations = {"e" : set(), "n" : set(), "s" : set(), "same" : set(), "r" : set()}

for singular, plural in plurals:
  if len(singular) == len(plural):
     formations["same"].add((singular, plural))
  elif plural.endswith("n"):
     formations["n"].add((singular, plural))
  elif plural.endswith("s"):
     formations["s"].add((singular, plural))
  elif plural.endswith("e"):
     formations["e"].add((singular, plural))
  elif plural.endswith("r"):
     formations["r"].add((singular, plural))
  else:
      print((singular, plural))

def doChoiceList(xs):
    for x in xs:
       print(x)
    losses = choiceList([encodeWord(x) for x in xs]) #, encodeWord(y))
    print(losses)
    return np.argmin(losses)


def doChoice(x, y):
    print(x)
    print(y)
    losses = choice(encodeWord(x), encodeWord(y))
    print(losses)
    return 0 if losses[0] < losses[1] else 1

TRAIN_SIZE = 20.0

# classify singulars vs plurals
print("trained on n, s, e")
encodedPlurals = encodeListOfWords(["."+y for x, y in plusL([formations["n"], formations["s"], formations["e"]])])
encodedSingulars = encodeListOfWords(["."+x for x, y in plusL([formations["n"], formations["s"], formations["e"]])])

predictors = encodedPlurals + encodedSingulars

dependent = [0 for _ in encodedSingulars] + [1 for _ in encodedPlurals]

from sklearn.model_selection import train_test_split
x_train, x_test, y_train, y_test = train_test_split(predictors, dependent, test_size=1-TRAIN_SIZE/len(dependent), random_state=0, shuffle=True, stratify=dependent)


from sklearn.linear_model import LogisticRegression

print("regression")

logisticRegr = LogisticRegression()

logisticRegr.fit(x_train, y_train)

predictions = logisticRegr.predict(x_test)


score = logisticRegr.score(x_test, y_test)
print(["test on n, s, e",score])

evaluationPoints = []
evaluationPoints.append(("NSE", "NSE", score))



# test on R plurals
encodedPluralsR = encodeListOfWords(["."+y for x, y in formations["r"]])
encodedSingularsR = encodeListOfWords(["."+x for x, y in formations["r"]])

predictors = encodedPluralsR + encodedSingularsR
dependent = [0 for _ in encodedSingularsR] + [1 for _ in encodedPluralsR]

score = logisticRegr.score(predictors, dependent)
print(["r plurals",score])

evaluationPoints.append(("NSE", "R", score))

# test on R plurals
encodedPluralsR = encodeListOfWords(["."+y for x, y in formations["same"]])
encodedSingularsR = encodeListOfWords(["."+x for x, y in formations["same"]])

predictors = encodedPluralsR + encodedSingularsR
dependent = [0 for _ in encodedSingularsR] + [1 for _ in encodedPluralsR]

score = logisticRegr.score(predictors, dependent)
print(["same length plurals", score])

evaluationPoints.append(("NSE", "same", score))




# adjective plural


#adjectivePlurals = set()
#
#for sentence in training.iterator():
# for line in sentence:
#   if line["posUni"] == "ADJ":
#      morph = line["morph"]
#      if "Number=Plur" in morph:
#          adjectivePlurals.add(line["word"].lower())
#          
#predictors = encodeListOfWords(["."+x for x in adjectivePlurals])
#dependent = [1 for _ in predictors]
#score = logisticRegr.score(predictors, dependent)
#print(["adjective plurals", score])
#
# now look at other words that end in n, s, e

wordsEndingIn = {"r" : set(), "s" : set(), "n" : set(), "e" : set()}

for sentence in training.iterator():
 for line in sentence:
   if line["posUni"] == "NOUN":
      morph = line["morph"]
      if "Number=Plur" not in  morph and "Case=Dat" not in morph:
        if line["word"][-1] in wordsEndingIn:
          wordsEndingIn[line["word"][-1]].add(line["word"].lower())

predictors = encodeListOfWords(["."+x for x in wordsEndingIn["r"]])
dependent = [0 for _ in predictors]
score = logisticRegr.score(predictors, dependent)
print(["r", score])

evaluationPoints.append(("NSE", "r_distract", score))



predictors = encodeListOfWords(["."+x for x in wordsEndingIn["s"]])
dependent = [0 for _ in predictors]
score = logisticRegr.score(predictors, dependent)
print(["s", score])

evaluationPoints.append(("NSE", "s_distract", score))



predictors = encodeListOfWords(["."+x for x in wordsEndingIn["n"]])
dependent = [0 for _ in predictors]
score = logisticRegr.score(predictors, dependent)
print(["n", score])

evaluationPoints.append(("NSE", "n_distract", score))




predictors = encodeListOfWords(["."+x for x in wordsEndingIn["e"]])
dependent = [0 for _ in predictors]
score = logisticRegr.score(predictors, dependent)
print(["e", score])

evaluationPoints.append(("NSE", "e_distract", score))





###################################
print("training on n,s")

encodedPlurals = encodeListOfWords(["."+y for x, y in plusL([formations["n"], formations["s"]])])
encodedSingulars = encodeListOfWords(["."+x for x, y in plusL([formations["n"], formations["s"]])])

predictors = encodedPlurals + encodedSingulars

dependent = [0 for _ in encodedSingulars] + [1 for _ in encodedPlurals]

from sklearn.model_selection import train_test_split
x_train, x_test, y_train, y_test = train_test_split(predictors, dependent, test_size=1-TRAIN_SIZE/len(dependent), random_state=0, shuffle=True, stratify=dependent)


from sklearn.linear_model import LogisticRegression

print("regression")

logisticRegr = LogisticRegression()

logisticRegr.fit(x_train, y_train)

predictions = logisticRegr.predict(x_test)


score = logisticRegr.score(x_test, y_test)
print(score)

evaluationPoints.append(("NS", "NS", score))



# test on R plurals
encodedPluralsR = encodeListOfWords(["."+y for x, y in formations["r"]])
encodedSingularsR = encodeListOfWords(["."+x for x, y in formations["r"]])

predictors = encodedPluralsR + encodedSingularsR
dependent = [0 for _ in encodedSingularsR] + [1 for _ in encodedPluralsR]

score = logisticRegr.score(predictors, dependent)
print(["r plurals",score])

evaluationPoints.append(("NS", "R", score))



# test on R plurals
encodedPluralsR = encodeListOfWords(["."+y for x, y in formations["same"]])
encodedSingularsR = encodeListOfWords(["."+x for x, y in formations["same"]])

predictors = encodedPluralsR + encodedSingularsR
dependent = [0 for _ in encodedSingularsR] + [1 for _ in encodedPluralsR]

score = logisticRegr.score(predictors, dependent)
print(["same length plurals",score])

evaluationPoints.append(("NS", "same", score))



predictors = encodeListOfWords(["."+x for x in wordsEndingIn["r"]])
dependent = [0 for _ in predictors]
score = logisticRegr.score(predictors, dependent)
print(["r", score])

evaluationPoints.append(("NS", "r_distract", score))



predictors = encodeListOfWords(["."+x for x in wordsEndingIn["s"]])
dependent = [0 for _ in predictors]
score = logisticRegr.score(predictors, dependent)
print(["s", score])

evaluationPoints.append(("NS", "s_distract", score))



predictors = encodeListOfWords(["."+x for x in wordsEndingIn["n"]])
dependent = [0 for _ in predictors]
score = logisticRegr.score(predictors, dependent)
print(["n", score])

evaluationPoints.append(("NS", "n_distract", score))




predictors = encodeListOfWords(["."+x for x in wordsEndingIn["e"]])
dependent = [0 for _ in predictors]
score = logisticRegr.score(predictors, dependent)
print(["e", score])


evaluationPoints.append(("NS", "e_distract", score))






###################################

print("training on n")
encodedPlurals = encodeListOfWords(["."+y for x, y in plusL([formations["n"]])])
encodedSingulars = encodeListOfWords(["."+x for x, y in plusL([formations["n"]])])

predictors = encodedPlurals + encodedSingulars

dependent = [0 for _ in encodedSingulars] + [1 for _ in encodedPlurals]

from sklearn.model_selection import train_test_split
x_train, x_test, y_train, y_test = train_test_split(predictors, dependent, test_size=1-TRAIN_SIZE/len(dependent), random_state=0, shuffle=True, stratify=dependent)


from sklearn.linear_model import LogisticRegression

print("regression")

logisticRegr = LogisticRegression()

logisticRegr.fit(x_train, y_train)

predictions = logisticRegr.predict(x_test)


score = logisticRegr.score(x_test, y_test)
print(["test on n plurals",score])

evaluationPoints.append(("N", "N", score))




# test on R plurals
encodedPluralsR = encodeListOfWords(["."+y for x, y in formations["r"]])
encodedSingularsR = encodeListOfWords(["."+x for x, y in formations["r"]])

predictors = encodedPluralsR + encodedSingularsR
dependent = [0 for _ in encodedSingularsR] + [1 for _ in encodedPluralsR]

score = logisticRegr.score(predictors, dependent)
print(["r plurals",score])

evaluationPoints.append(("N", "R", score))



# test on R plurals
encodedPluralsR = encodeListOfWords(["."+y for x, y in formations["same"]])
encodedSingularsR = encodeListOfWords(["."+x for x, y in formations["same"]])

predictors = encodedPluralsR + encodedSingularsR
dependent = [0 for _ in encodedSingularsR] + [1 for _ in encodedPluralsR]

score = logisticRegr.score(predictors, dependent)
print(score)

evaluationPoints.append(("N", "same", score))


# test on R plurals
encodedPluralsR = encodeListOfWords(["."+y for x, y in formations["e"]])
encodedSingularsR = encodeListOfWords(["."+x for x, y in formations["e"]])

predictors = encodedPluralsR + encodedSingularsR
dependent = [0 for _ in encodedSingularsR] + [1 for _ in encodedPluralsR]

score = logisticRegr.score(predictors, dependent)
print(["e plurals",score])

evaluationPoints.append(("N", "E", score))



# test on R plurals
encodedPluralsR = encodeListOfWords(["."+y for x, y in formations["s"]])
encodedSingularsR = encodeListOfWords(["."+x for x, y in formations["s"]])

predictors = encodedPluralsR + encodedSingularsR
dependent = [0 for _ in encodedSingularsR] + [1 for _ in encodedPluralsR]

score = logisticRegr.score(predictors, dependent)
print(["s plurals",score])

evaluationPoints.append(("N", "S", score))

predictors = encodeListOfWords(["."+x for x in wordsEndingIn["r"]])
dependent = [0 for _ in predictors]
score = logisticRegr.score(predictors, dependent)
print(["r", score])


evaluationPoints.append(("N", "r_distract", score))



predictors = encodeListOfWords(["."+x for x in wordsEndingIn["s"]])
dependent = [0 for _ in predictors]
score = logisticRegr.score(predictors, dependent)
print(["s", score])

evaluationPoints.append(("N", "s_distract", score))



predictors = encodeListOfWords(["."+x for x in wordsEndingIn["n"]])
dependent = [0 for _ in predictors]
score = logisticRegr.score(predictors, dependent)
print(["n", score])

evaluationPoints.append(("N", "n_distract", score))




predictors = encodeListOfWords(["."+x for x in wordsEndingIn["e"]])
dependent = [0 for _ in predictors]
score = logisticRegr.score(predictors, dependent)
print(["e", score])

evaluationPoints.append(("N", "e_distract", score))





###################################

print("training on same")
encodedPlurals = encodeListOfWords(["."+y for x, y in plusL([formations["same"]])])
encodedSingulars = encodeListOfWords(["."+x for x, y in plusL([formations["same"]])])

predictors = encodedPlurals + encodedSingulars

dependent = [0 for _ in encodedSingulars] + [1 for _ in encodedPlurals]

print("regression")

logisticRegr = LogisticRegression()

logisticRegr.fit(predictors, dependent)

# test on R plurals
encodedPluralsR = encodeListOfWords(["."+y for x, y in formations["r"]])
encodedSingularsR = encodeListOfWords(["."+x for x, y in formations["r"]])

predictors = encodedPluralsR + encodedSingularsR
dependent = [0 for _ in encodedSingularsR] + [1 for _ in encodedPluralsR]

score = logisticRegr.score(predictors, dependent)
print(["r plurals",score])

evaluationPoints.append(("same", "R", score))



# test on R plurals
encodedPluralsR = encodeListOfWords(["."+y for x, y in formations["n"]])
encodedSingularsR = encodeListOfWords(["."+x for x, y in formations["n"]])

predictors = encodedPluralsR + encodedSingularsR
dependent = [0 for _ in encodedSingularsR] + [1 for _ in encodedPluralsR]

score = logisticRegr.score(predictors, dependent)
print(["n plurals",score])

evaluationPoints.append(("same", "N", score))



# test on R plurals
encodedPluralsR = encodeListOfWords(["."+y for x, y in formations["e"]])
encodedSingularsR = encodeListOfWords(["."+x for x, y in formations["e"]])

predictors = encodedPluralsR + encodedSingularsR
dependent = [0 for _ in encodedSingularsR] + [1 for _ in encodedPluralsR]

score = logisticRegr.score(predictors, dependent)
print(["e plurals",score])

evaluationPoints.append(("same", "E", score))



# test on R plurals
encodedPluralsR = encodeListOfWords(["."+y for x, y in formations["s"]])
encodedSingularsR = encodeListOfWords(["."+x for x, y in formations["s"]])

predictors = encodedPluralsR + encodedSingularsR
dependent = [0 for _ in encodedSingularsR] + [1 for _ in encodedPluralsR]

score = logisticRegr.score(predictors, dependent)
print(["s plurals",score])

evaluationPoints.append(("same", "S", score))


with open("/checkpoint/mhahn/trajectories/"+__file__+"_"+args.load_from, "w") as outFile:
   for line in evaluationPoints:
     outFile.write("\t".join(list(map(str, (line))))+"\n")



quit()



for key in formations:
    print(key, len(formations[key]))



resultsSg = [0, 0]
resultsPl = [0, 0]

counter = 0
for singular, plural in formations["e"]:
     counter += 1
#     results[doChoiceList([".der"+noun+".", ".die"+noun+".", ".das"+noun+"."])] += 1
     resultsSg[doChoiceList(["."+singular+"istgut.", "."+singular+"sindgut."])] += 1
     resultsPl[doChoiceList(["."+plural+"istgut.", "."+plural+"sindgut."])] += 1


     print([x/counter for x in resultsSg])
     print([x/counter for x in resultsPl])



quit()


out1, hidden1 = encodeSequenceBatchForward(encodeWord("katze"))
out2, hidden2 = encodeSequenceBatchForward(encodeWord("katzem"))
#print(torch.dot(out1[-1], out2[-1]))
#print(torch.dot(hidden1[0], hidden2[0]))
#print(torch.dot(hidden1[1], hidden2[1]))

print(torch.nn.functional.cosine_similarity(out1, out2, dim=0))
#print(torch.nn.functional.cosine_similarity(hidden1, hidden2, dim=0))
#print(torch.nn.functional.cosine_similarity(cell1, cell2, dim=0))

print("willmach")
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".ichmach"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".dumach"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".ermach"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".siemach"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".esmach"))))

print(keepGenerating(encodeSequenceBatchForward(encodeWord(".ichmach"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".dumach"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".ermach"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".siemach"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".esmach"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".esdenk"))))

doChoice(".ichmachedas.", ".ichmachstdas.")
doChoice(".dumachendas.", ".dumachstdas.")
doChoice(".ermachendas.", ".ermachtdas.")
doChoice(".wirmachendas.", ".wirmachtdas.")

doChoice(".ichvergeigedas.", ".ichvergeigstdas.")
doChoice(".duvergeigendas.", ".duvergeigstdas.")
doChoice(".ervergeigendas.", ".ervergeigtdas.")
doChoice(".wirvergeigendas.", ".wirvergeigtdas.")





doChoice(".ichwilldas.", ".ichwillstdas.")
doChoice(".duwollendas.", ".duwillstdas.")
doChoice(".erwollendas.", ".erwilldas.")
doChoice(".wirwollendas.", ".wirwilldas.")


doChoice("indashaus.", "indiehaus.")
doChoice("indascomputermaus.", "indiecomputermaus.")

doChoice(".ichgeheindashaus.", ".ichgeheindemhaus.")
doChoice(".ichlebeindashaus.", ".ichlebeindemhaus.")


doChoice(".ichlebeindashausmeisterzimmer.", ".ichlebeindemhausmeisterzimmer.")


doChoice(".zweihaus.", ".zweihäuser.")
doChoice(".zweilampen.", ".zweilampe.")
doChoice(".zweilampenpfahl.", ".zweilampenpfähle.")
doChoice(".zweihauspfähle.", ".zweihäuserpfähle.")
doChoice(".zweinasenbär.", ".zweinasenbären.")

doChoice(".einhaus.", ".einhäuser.")
doChoice(".einlampenpfahl.", ".einlampenpfähle.")
doChoice(".einhauspfähle.", ".einhäuserpfähle.")
doChoice(".einnasenbär.", ".einnasenbären.")

#genderTest()


quit()


print(keepGenerating(encodeSequenceBatchForward(encodeWord(".ichwillmach"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".ichhabegemach"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".ichhabegepups"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".ichhabegegurk"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".ichhabegerief"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".ichwerdepups"))))
print("Katze")
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".einekatze"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".zweikatze"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".derkater"))))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".deskater"))))

print(keepGenerating(encodeSequenceBatchForward(encodeWord(".katze")),backwards=False))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".kater")),backwards=False))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".hund")),backwards=False))
print(keepGenerating(encodeSequenceBatchForward(encodeWord(".neben")),backwards=False))



quit()
                  
def padWords(words):
   maxLength = max([len(x) for x in words])
   for i, word in enumerate(words):
      if len(word) < maxLength:
         words[i] = ([0] * (maxLength - len(word))) + word #word.append(0)
   return words


# TODO train ght eRNN so that it is actually used to seeing 0's in the beginning of a sequence

def getEncodingsForList(wordsToBeEncoded):
    return getEncodingsForListGeneral(wordsToBeEncoded, encodeSequenceBatchForward)



def getEncodingsForListGeneral(wordsToBeEncoded, encodingFunction):
    modelVectors = []
    byLength = sorted(list(wordsToBeEncoded), reverse=True)

    for offset in range(0, len(wordsToBeEncoded), 100):
#      print(offset)
      codes1, codes2 = encodingFunction(padWords([encodeWord(word)[0] for word in byLength[offset:offset+100]]))
      for index, word in enumerate(byLength[offset:offset+100]):
         code1 = codes1[index].cpu()#,len(word)]
         code2 = codes2[0][0,index].cpu()#,len(word)]
         code3 = codes2[1][0,index].cpu()#,len(word)]
         modelVectors.append((code1, (code2, code3)))
    #     print((code1,code2,code3))
    return modelVectors





#pluralWords = []
#singularWords = []
#for word in plurals:
#   singularWords.append(word[0])
#   pluralWords.append(word[1])
#
#plur = getEncodingsForList(pluralWords)
#sing = getEncodingsForList(singularWords)
#
#
#print("Concatenating")
#
#predictors = []
#dependent = []
#for vectors in plus(sing, plur):
#     code = vectors[0] #torch.cat(vectors, dim=0)
#    # print(code)
#     predictors.append(code.data.cpu().numpy())
#for _ in sing:
#  dependent.append(0)
#for _ in plur:
#  dependent.append(1)
# 
#
## create logistic regression for gender
#
#from sklearn.model_selection import train_test_split
#x_train, x_test, y_train, y_test = train_test_split(predictors, dependent, test_size=0.1, random_state=0, shuffle=True)
#
#
#from sklearn.linear_model import LogisticRegression
#
#print("regression")
#
#logisticRegr = LogisticRegression()
#
#logisticRegr.fit(x_train, y_train)
#
#predictions = logisticRegr.predict(x_test)
#
#
#score = logisticRegr.score(x_test, y_test)
#print(score)
#




######################################

print(genders)

# create a dictionary of encodings of all words

# then see whether things are more predictable from LM than from baseline

wordsToBeEncoded = genders["Gender=Neut"]

baselineVectors = []

print(len(genders["Gender=Fem"]))
print(len(genders["Gender=Masc"]))

fem = getEncodingsForList(random.sample(genders["Gender=Fem"], 1000))
masc = getEncodingsForList(random.sample(genders["Gender=Masc"], 1000))

## so initial 0 will look like dropout
#char_embeddings.data[0] = 0 * char_embeddings.data[0]

print("Concatenating")

predictors = []
dependent = []
for vectors in plus(fem, masc):
     code = vectors[0] #torch.cat(vectors, dim=0)
    # print(code)
     predictors.append(code.data.cpu().numpy())
for _ in fem:
  dependent.append(0)
for _ in masc:
  dependent.append(1)
     

# create logistic regression for gender

from sklearn.model_selection import train_test_split
x_train, x_test, y_train, y_test = train_test_split(predictors, dependent, test_size=1-TRAIN_SIZE/len(dependent), random_state=0, shuffle=True, stratify=dependent)


from sklearn.linear_model import LogisticRegression

print("regression")

logisticRegr = LogisticRegression()

logisticRegr.fit(x_train, y_train)

predictions = logisticRegr.predict(x_test)


score = logisticRegr.score(x_test, y_test)
print(score)






