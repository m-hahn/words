from paths import WIKIPEDIA_HOME
from paths import LOG_HOME
from paths import CHAR_VOCAB_HOME
from paths import MODELS_HOME


# train on verbs, test on nouns 


#python char-lm-ud-wiki-classify-boundaries-nouns_verbs.py --language german --batchSize 128 --char_embedding_size 100 --hidden_dim 1024 --layer_num 2 --weight_dropout_in 0.1 --weight_dropout_hidden 0.35 --char_dropout_prob 0.0 --char_noise_prob 0.01 --learning_rate 0.2 --load-from wiki-german-nospaces-bugfix


import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--language", dest="language", type=str)
parser.add_argument("--load-from", dest="load_from", type=str)

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


assert args.language == "german"


import corpusIteratorWiki



from corpusIterator import CorpusIterator

if True:
   training = CorpusIterator("German", partition="train", storeMorph=True, removePunctuation=True)
   vocabulary = {"NOUN" : set(), "VERB" : set()}
   for sentence in training.iterator():
       for line in sentence:
        if line["posUni"] in vocabulary:
          vocabulary[line["posUni"]].add(line["word"].lower())
#   print(vocabulary)
#quit()
#genderTest()

vocabulary["NOUN"] = vocabulary["NOUN"].difference(vocabulary["VERB"])
vocabulary["VERB"] = vocabulary["VERB"].difference(vocabulary["NOUN"])




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

parameters_cached = [x for x in parameters()]

optim = torch.optim.SGD(parameters(), lr=args.learning_rate, momentum=0.0) # 0.02, 0.9

named_modules = {"rnn" : rnn, "output" : output, "char_embeddings" : char_embeddings, "optim" : optim}

if args.load_from is not None:
  checkpoint = torch.load(MODELS_HOME+"/"+args.load_from+".pth.tar")
  for name, module in named_modules.items():
      module.load_state_dict(checkpoint[name])

from torch.autograd import Variable


# ([0] + [stoi[training_data[x]]+1 for x in range(b, b+sequence_length) if x < len(training_data)]) 

#from embed_regularize import embedded_dropout


def prepareDatasetChunks(data, train=True):
      numeric = [0]
      boundaries = [None for _ in range(args.sequence_length+1)]
      count = 0
      currentWord = ""
      print("Prepare chunks")
      for chunk in data:
       print(len(chunk))
       for char in chunk:
         if char == " ":
           boundaries[len(numeric)] = currentWord
           currentWord = ""
           continue
         count += 1
         currentWord += char
#         if count % 100000 == 0:
#             print(count/len(data))
         numeric.append((stoi[char]+3 if char in stoi else 2) if (not train) or random.random() > args.char_noise_prob else 2+random.randint(0, len(itos)))
         if len(numeric) > args.sequence_length:
            yield numeric, boundaries
            numeric = [0]
            boundaries = [None for _ in range(args.sequence_length+1)]





#def prepareDataset(data, train=True):
#      numeric = [0]
#      count = 0
#      for char in data:
#         if char == " ":
#           continue
#         count += 1
##         if count % 100000 == 0:
##             print(count/len(data))
#         numeric.append((stoi[char]+3 if char in stoi else 2) if (not train) or random.random() > args.char_noise_prob else 2+random.randint(0, len(itos)))
#         if len(numeric) > args.sequence_length:
#            yield numeric
#            numeric = [0]
#

# from each bath element, get one positive example OR one negative example

wordsSoFar = set()
hidden_states = []
labels = []
pos = []

def forward(numeric, train=True, printHere=False):
      numeric, boundaries = zip(*numeric)
#      print(numeric)
 #     print(boundaries)

      input_tensor = Variable(torch.LongTensor(numeric).transpose(0,1)[:-1].cuda(), requires_grad=False)
      target_tensor = Variable(torch.LongTensor(numeric).transpose(0,1)[1:].cuda(), requires_grad=False)

      embedded = char_embeddings(input_tensor)
      if train:
         embedded = char_dropout(embedded)

      out, _ = rnn_drop(embedded, None)
#      if train:
#          out = dropout(out)

      for i in range(len(boundaries)):
         target = (random.random() < 0.5)
#         print(boundaries[i])
#        print(target)
#         print(boundaries[i]) 
         def accepted(x):
             return  (((x is None if target == False else (x not in wordsSoFar and (x in vocabulary["NOUN"] or x in vocabulary["VERB"])))))
         true = sum([accepted(x) for x in boundaries[i][int(args.sequence_length/2):-1]])
 #        print(target, true)
         if true == 0:
            continue
         soFar = 0
         for j in range(len(boundaries[i])):
           if j < int(len(boundaries[i])/2):
               continue
           if accepted(boundaries[i][j]):
 #             print(i, target, true,soFar)
              if random.random() < 1/(true-soFar):
                  hidden_states.append(out[j,i].detach().data.cpu().numpy())
                  labels.append(1 if target else 0)
                  if target:
                     wordsSoFar.add(boundaries[i][j])
                     pos.append("NOUN" if boundaries[i][j] in vocabulary["NOUN"] else "VERB")
                  else:
                     pos.append(None)
                  break
              soFar += 1
         assert soFar < true
#      print(hidden_states)
#      print(labels)

      logits = output(out) 
      log_probs = logsoftmax(logits)
   #   print(logits)
  #    print(log_probs)
 #     print(target_tensor)

      loss = train_loss(log_probs.view(-1, len(itos)+3), target_tensor.view(-1))

      if printHere:
         lossTensor = print_loss(log_probs.view(-1, len(itos)+3), target_tensor.view(-1)).view(args.sequence_length, len(numeric))
         losses = lossTensor.data.cpu().numpy()
#         boundaries_index = [0 for _ in numeric]
         for i in range((args.sequence_length-1)-1):
 #           if boundaries_index[0] < len(boundaries[0]) and i+1 == boundaries[0][boundaries_index[0]]:
  #             boundary = True
   #            boundaries_index[0] += 1
    #        else:
     #          boundary = False
            print((losses[i][0], itos[numeric[0][i+1]-3]))
         print(len(labels))
     # return loss, len(numeric) * args.sequence_length



import time

devLosses = []
#for epoch in range(10000):
if True:
   training_data = corpusIteratorWiki.training(args.language)
   print("Got data")
   training_chars = prepareDataset(training_data, train=True) if args.language == "italian" else prepareDatasetChunks(training_data, train=True)



   rnn_drop.train(False)
   startTime = time.time()
   trainChars = 0
   counter = 0
   while True:
      counter += 1
      try:
         numeric = [next(training_chars) for _ in range(args.batchSize)]
      except StopIteration:
         break
      printHere = (counter % 50 == 0)
      forward(numeric, printHere=printHere, train=True)
      #backward(loss, printHere)
      if printHere:
          print((counter))
          print("Dev losses")
          print(devLosses)
          print("Chars per sec "+str(trainChars/(time.time()-startTime)))

      if len(labels) > 10000:
         break

predictors = hidden_states
dependent = labels


x_train = []
x_test = []
y_train = []
y_test = []
for i in range(len(labels)):
    if pos[i] == None:
        partition = ("test" if random.random() < 0.1 else "train")
    elif pos[i] == "VERB":
        partition = "test"
    elif pos[i]:
         partition = "train"
    else:
           assert False
    if partition == "test":
       x_test.append(predictors[i])
       y_test.append(labels[i])
    else:
       x_train.append(predictors[i])
       y_train.append(labels[i])


from sklearn.linear_model import LogisticRegression

print("regression")

logisticRegr = LogisticRegression()

logisticRegr.fit(x_train, y_train)

predictions = logisticRegr.predict(x_test)


score = logisticRegr.score(x_test, y_test)
print(score)






#   dev_data = corpusIteratorWiki.dev(args.language)
#   print("Got data")
#   dev_chars = prepareDataset(dev_data, train=True) if args.language == "italian" else prepareDatasetChunks(dev_data, train=True)
#
#
#     
#   dev_loss = 0
#   dev_char_count = 0
#   counter = 0
#
#   while True:
#       counter += 1
#       try:
#          numeric = [next(dev_chars) for _ in range(args.batchSize)]
#       except StopIteration:
#          break
#       printHere = (counter % 50 == 0)
#       loss, numberOfCharacters = forward(numeric, printHere=printHere, train=False)
#       dev_loss += numberOfCharacters * loss.cpu().data.numpy()[0]
#       dev_char_count += numberOfCharacters
#   devLosses.append(dev_loss/dev_char_count)
#   print(devLosses)
#   with open(LOG_HOME+"/"+args.language+"_"+__file__+"_"+str(args.myID), "w") as outFile:
#      print(" ".join([str(x) for x in devLosses]), file=outFile)
#
#   if len(devLosses) > 1 and devLosses[-1] > devLosses[-2]:
#      break
#

