from paths import WIKIPEDIA_HOME
from paths import CHAR_VOCAB_HOME
from paths import FIGURES_HOME
from paths import MODELS_HOME
errors = 0
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--language", dest="language", type=str)
parser.add_argument("--load-from", dest="load_from", type=str)
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
parser.add_argument("--sequence_length", type=int, default=random.choice([50, 50, 80]))
parser.add_argument("--verbose", type=bool, default=False)
parser.add_argument("--lr_decay", type=float, default=random.choice([0.5, 0.7, 0.9, 0.95, 0.98, 0.98, 1.0]))

import math

args=parser.parse_args()
print(args)


assert args.language == "german"




import corpusIteratorWikiWords



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
itos.append("\n")
itos.append(" ")
print(itos)
stoi = dict([(itos[i],i) for i in range(len(itos))])

halfSequenceLength = int(args.sequence_length/2)



import random


import torch

print(torch.__version__)

from weight_drop import WeightDrop


rnn = torch.nn.LSTM(args.char_embedding_size, args.hidden_dim, args.layer_num).cuda()

rnn_parameter_names = [name for name, _ in rnn.named_parameters()]
print(rnn_parameter_names)
#quit()


rnn_drop = WeightDrop(rnn, [(name, args.weight_dropout_in) for name, _ in rnn.named_parameters() if name.startswith("weight_ih_")] + [ (name, args.weight_dropout_hidden) for name, _ in rnn.named_parameters() if name.startswith("weight_hh_")])


sizeOfVocabularyRelevant = len(itos)-1+3-1
print(sizeOfVocabularyRelevant)
# -1, because whitespace doesn't actually appear
output = torch.nn.Linear(args.hidden_dim, sizeOfVocabularyRelevant).cuda()
char_embeddings = torch.nn.Embedding(num_embeddings=sizeOfVocabularyRelevant, embedding_dim=args.char_embedding_size).cuda()

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


#data = AcqdivReaderPartition(acqdivCorpusReader, partition="train").reshuffledIterator(blankBeforeEOS=False)

rnn_drop.train(False)


data = corpusIteratorWikiWords.dev(args.language)
print("Got data")



numeric_with_blanks = []
count = 0
print("Prepare chunks")
for chunk in data:
  for word in chunk:
    numeric_with_blanks.append(stoi[" "]+3)
    for char in word:
  #    print((char if char != "\n" else "\\n", stoi[char]+3 if char in stoi else 2))
      count += 1
   #   if char not in stoi:
   #       print(char)
      numeric_with_blanks.append(stoi[char]+3 if char in stoi else 2)

# select a portion
numeric_with_blanks = numeric_with_blanks[:1000000]



boundaries = []
numeric_full = []
for entry in numeric_with_blanks:
 # print((entry-3, itos[entry-3]))
  #assert entry > 3
  if entry > 3 and itos[entry-3] == " ":
     boundaries.append(len(numeric_full))
  else:
     numeric_full.append(entry)

heights = [0 for _ in numeric_full]

positionNumeric = 0

with open(WIKIPEDIA_HOME+"german-valid-tagged-parsed.txt", "r") as inFile:
  for line in inFile:
     if positionNumeric >= len(numeric_full):
        print("at end")
        break
     line = line.strip()[2:-1]
     start = 0
     bracketHeight = 0
     if line[0] != "(" and len(line) == 1:
          continue
     line = line + "(HALLO NOTHING)"     
     while positionNumeric < len(numeric_full):
        assert line[start] == "(", (line, line[start:])
        assert line[start+1] != " "
        nextStart = line.find(" (", start+1)+1
        nextBlank = line.find(" ", start+1)
        if nextStart == 0 or nextBlank == -1:
            break
        if nextStart == nextBlank + 1: # (CATEGORY (
            bracketHeight += 1
            start = nextStart
        elif nextStart > nextBlank and line[nextStart-1] == " ": # (CATEGORY word)* (
           if positionNumeric >= len(numeric_full):
                     print("at end")
                     break
           heights[positionNumeric] = bracketHeight
           bracketHeight = 0
           nextWordEnd = line.find(") ", start+1)
           i = nextWordEnd
           while line[i] == ")":
              bracketHeight += 1
              i -= 1
           newWord = line[nextBlank+1:i+1]
           if positionNumeric >= len(numeric_full):
                     print("at end")
                     break
           if True:
               print((newWord, "".join([itos[numeric_full[x]-3] for x in range(positionNumeric, min(len(numeric_full), positionNumeric+len(newWord)))])))
           if newWord == "<nowiki>" or newWord == "</nowiki>" or newWord == "<br>":
                 print("REMOVED TAG")
           else:              
              for char in newWord:
                 if positionNumeric >= len(numeric_full):
                        print("at end")
                        break
                 while itos[numeric_full[positionNumeric]-3] in ["(", ")"] and char != itos[numeric_full[positionNumeric]-3] :
                    positionNumeric+=1
                    if positionNumeric >= len(numeric_full):
                        print("at end")
                        break
                 if positionNumeric >= len(numeric_full):
                        print("at end")
                        break
                 #print((char, itos[numeric_full[positionNumeric]-3]))
                 jumping = 0
                 while char.lower() !=                itos[numeric_full[positionNumeric]-3].lower() and numeric_full[positionNumeric] != 2:
                     jumping += 1
                     #print(jumping)
                     #print(newWord, [itos[numeric_full[x]-3].lower() for x in range(positionNumeric, positionNumeric+5)])
                     positionNumeric += 1
                     if positionNumeric >= len(numeric_full):
                        print("at end")
                        break
                 assert jumping < 500
                 positionNumeric+=1
                 if positionNumeric >= len(numeric_full):
                        print("at end")
                        break
           if positionNumeric >= len(numeric_full):
                     print("at end")
                     break
           assert nextWordEnd+2 == nextStart
#           assert line[i] == " ", line[i:]
 #          assert i + 1 == nextStart
           start = nextStart
        else:
            assert False, (">>>"+line[start:], start, nextStart, nextBlank)
        if positionNumeric >= len(numeric_full):
                     print("at end")
                     break


future_surprisal_with = [None for _ in numeric_full]
future_surprisal_without = [None for _ in numeric_full]

char_surprisal = [None for _ in numeric_full]
char_entropy = [None for _ in numeric_full]

for start in range(0, len(numeric_full)-args.sequence_length, args.batchSize):
      numeric = [([0] + numeric_full[b:b+args.sequence_length]) for b in range(start, start+args.batchSize)]
      maxLength = max([len(x) for x in numeric])
      for i in range(len(numeric)):
        numeric[i] = numeric[i] + [0]*(maxLength-len(numeric[i]))

      input_tensor = Variable(torch.LongTensor(numeric).transpose(0,1)[:-1].cuda(), requires_grad=False)
      target_tensor = Variable(torch.LongTensor(numeric).transpose(0,1)[1:].cuda(), requires_grad=False)
      embedded = char_embeddings(input_tensor)

      out, _ = rnn_drop(embedded, None)
      logits = output(out) 
      log_probs = logsoftmax(logits)

      entropy = (- log_probs * torch.exp(log_probs)).sum(2).view((maxLength-1), args.batchSize).data.cpu().numpy()

      loss = print_loss(log_probs.view(-1, sizeOfVocabularyRelevant), target_tensor.view(-1)).view((maxLength-1), args.batchSize)
      losses = loss.data.cpu().numpy()

      for i in range(start, start+args.batchSize):
         surprisalAtStart = losses[:halfSequenceLength,i-start].sum()
         surprisalAtMid = losses[halfSequenceLength:, i-start].sum()
         if i+halfSequenceLength < len(future_surprisal_with):
            future_surprisal_with[i+halfSequenceLength] = surprisalAtMid
            char_surprisal[i+halfSequenceLength] = losses[halfSequenceLength, i-start]
            char_entropy[i+halfSequenceLength] = entropy[halfSequenceLength, i-start]
         if i < len(future_surprisal_without):
            future_surprisal_without[i] = surprisalAtStart
             
def mi(x,y):
  return   x-y if x is not None and y is not None else None

chars = []
predictor = []
dependent = []

utteranceBoundaries = []
lastWasUtteranceBoundary = False


conflicts = 0
boundaryCount = 0

boundaries_index = 0

height_dependent = []

for i in range(len(numeric_full)):
   assert conflicts < 100 or conflicts/(1+boundaries_index) < 0.1, conflicts
   if boundaries_index < len(boundaries) and i == boundaries[boundaries_index]:
      boundary = True
      boundaries_index += 1
      if heights[i] == 0:
         conflicts += 1

   else:
      if heights[i] > 0:
          conflicts += 1
      boundary = False
#   if conflicts > 1000:
#       assert False


   print((i, boundary, heights[i], conflicts, conflicts/(1+boundaries_index)))


   pmiFuturePast = mi(future_surprisal_without[i], future_surprisal_with[i])
#   print((itos[numeric_full[i]-3], char_surprisal[i], pmiFuturePast, pmiFuturePast < 0 if pmiFuturePast is not None else None, boundary)) # pmiFuturePast < 2 if pmiFuturePast is not None else None,
   if pmiFuturePast is not None:
     character = itos[numeric_full[i]-3] if numeric_full[i] != 2 else itos[-3]
     assert character != " "
     if character == "\n":
        lastWasUtteranceBoundary = True
     else:
       chars.append(character)
       predictor.append([pmiFuturePast, char_surprisal[i], char_entropy[i], 1 if lastWasUtteranceBoundary else 0]) #char_surprisal[i], pmiFuturePast]) #pmiFuturePast])
       dependent.append(1 if boundary else 0)
       lastWasUtteranceBoundary = False
       height_dependent.append(heights[i])

#assert len(height_dependent) == len(dependent)
#print(1234)

#quit()

#joint = list(zip(height_dependent, dependent))[:200]
#for a in joint:
#  print(a)
#quit()

# TODO exclude utterance boundaries from the logistic classification, and record where they were


# , char_surprisal[i], char_entropy[i]

# char_surprisal[i], 

#print(predictor)
#print(dependent)

zeroPredictor = [0]*len(predictor[0])

predictorShiftedP1 = predictor[1:]+[zeroPredictor]
predictorShiftedP2 = predictor[2:]+[zeroPredictor,zeroPredictor]
predictorShiftedP3 = predictor[3:]+[zeroPredictor,zeroPredictor,zeroPredictor]
predictorShiftedP4 = predictor[4:]+[zeroPredictor,zeroPredictor,zeroPredictor,zeroPredictor]

predictorShiftedM1 = [zeroPredictor]+predictor[:-1]
predictorShiftedM2 = [zeroPredictor,zeroPredictor]+predictor[:-2]
predictorShiftedM3 = [zeroPredictor,zeroPredictor,zeroPredictor]+predictor[:-3]
predictorShiftedM4 = [zeroPredictor,zeroPredictor,zeroPredictor,zeroPredictor]+predictor[:-4]

predictor = [a+b+c+d+e+f+g for a, b, c, d, e, f, g in zip(predictor, predictorShiftedP1, predictorShiftedP2, predictorShiftedP3, predictorShiftedM1, predictorShiftedM2, predictorShiftedM3)]



  
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt

import numpy as np
 

for height in range(0,10):
   predictor1 = [predictor[i] for i in range(len(predictor)) if height_dependent[i] == height]
   if  len(predictor1) < 1000:
      break
   print(len(predictor1))   
   
#   print(len(predictor1))
#   print(len(predictor2))
   predictor1 = np.array(predictor1, dtype=np.float32)
   
   predictor1 = predictor1.reshape((-1, 7, 4))
   
   
#   print(predictor1)
#   print(type(predictor1))
   average1 = np.array(predictor1.mean(axis=0))
#   print(type(average1))
#   print(average1)
#   print(average1)
#   print(average2)
   index = [0, 1, 2, 3, -1, -2, -3]
   
   
   pmis1 = predictor1[:,:,0]
   surprisals1 = predictor1[:,:,1]
   entropies1 = predictor1[:,:,2]
   
#   print(pmis1)
 #  print(surprisals1)
  # print(entropies1)
   
  
#   print(pmis2)
#   print(surprisals2)
#   print(entropies2)
   
  
   
   #for i in range(len(pmis1)):
   #      plt.plot(range(-3, 4), [pmis1[i, index.index(j)] for j in range(-3,4)], label=name, color="grey", alpha=0.1)
   averagePMI1 = pmis1.mean(axis=0)
#   plt.plot(range(-3, 4), [averagePMI1[index.index(j)] for j in range(-3,4)], label=str(height), linewidth=4.0)

   # now get a bootstrapped CI
   boot = 100
   yerr = [[None for _ in range(-3,4)] for _ in range(2)]
   replicateMeans = [[None for _ in range(boot)] for _ in range(-3, 4)]
   for w in range(boot):
     replicateInd = [random.randint(0, len(pmis1)-1) for _ in pmis1]
     replicate = pmis1[replicateInd,:]
     for q in range(-3, 4):
        replicateMeans[q][w] = replicate[:,q].mean(axis=0)
   for q in range(-3, 4):
#      print(q)
 #     print(replicateMeans[q])
      replicateMeans[q] = sorted(replicateMeans[q])
      lower = replicateMeans[q][int(0.05*boot)]
      upper = replicateMeans[q][int(0.95*boot)]
      yerr[0][q] = averagePMI1[q] - lower
      yerr[1][q] = upper - averagePMI1[q]
   plt.errorbar(range(-3, 4), [averagePMI1[index.index(j)] for j in range(-3,4)], yerr=yerr, label=str(height), linewidth=1.5)


plt.legend()
plt.show()
plt.savefig(FIGURES_HOME+"/segmentation-profile-pmis-"+args.language+"-all-heights-ci.pdf", bbox_inches='tight')
plt.close()
   
   

quit()



from sklearn.model_selection import train_test_split
x_train, x_test, y_train, y_test, chars_train, chars_test = train_test_split(predictor, height_dependent, chars, test_size=0.5, random_state=0, shuffle=False)


from sklearn.linear_model import LogisticRegression

logisticRegr = LogisticRegression()

logisticRegr.fit(x_train, y_train)

# Returns a NumPy Array
# Predict for One Observation (image)

predictions = logisticRegr.predict(x_test)
#predictions = [1 if x[0]<0 else 0 for x in x_test]
#print(predictions)

for char, predicted, real, predictor in zip(chars_test, predictions, y_test, x_test):
    print((char, predicted, real, predictor[0]))

realLexicon = set()
extractedLexicon = {}
currentWord = ""
currentWordReal = ""
realWords = 0
predictedWords = 0
agreement = 0


for char, predicted, real in zip(chars_test, predictions, y_test):
   assert char != " "
   if real ==1:
       realWords += 1
       if predicted == 1 and currentWord == currentWordReal:
           agreement += 1
       realLexicon.add(currentWordReal)
       currentWordReal = char
   else:
       currentWordReal += char

   if predicted == 1:
       predictedWords += 1
       extractedLexicon[currentWord] = extractedLexicon.get(currentWord, 0) + 1
       currentWord = char
   else:
       currentWord += char

print("Extracted words")
print(sorted(list(extractedLexicon.items()), key=lambda x:x[1]))
print("Incorrect Words")
incorrectWords = [(x,y) for (x,y) in extractedLexicon.items() if x in set(list(extractedLexicon)).difference(realLexicon)]
print(sorted(incorrectWords, key=lambda x:x[1]))
print("Correct words")
correctWords = [(x,y) for (x,y) in extractedLexicon.items() if x in set(list(extractedLexicon)).intersection(realLexicon)]
print(sorted(correctWords, key=lambda x:x[1]))
print("Lexicon")
print("Precision")
print(len(correctWords)/len(extractedLexicon))
print("Recall")
print(len(correctWords)/len(realLexicon))
print("..")

print("quality")
print("Precision")
print(agreement/predictedWords)
print("Recall")
print(agreement/realWords)



# P 27.51 R 42.38 F 33.37 BP 54.29 BR 85.53 BF 66.42 LP 46.9 LR 2.561 LF 4.856

precision = agreement/predictedWords
recall = agreement/realWords
f = 2*(precision*recall)/(precision+recall)

predictedBoundariesTotal = 0
predictedBoundariesCorrect = 0
realBoundariesTotal = 0

predictedAndReal = len([1 for x, y in zip(predictions, y_test) if x==1 and x==y])
predictedCount = sum(predictions)
targetCount = sum(y_test)
print("Boundaries")
print("Precision")
print(predictedAndReal/predictedCount)
print("Recall")
print(predictedAndReal/targetCount)

score = logisticRegr.score(x_test, y_test)
print(score)
bp = predictedAndReal/predictedCount
br = predictedAndReal/targetCount
bf = 2*bp*br/(bp+br)

lr = len(correctWords)/len(extractedLexicon)
lp = len(correctWords)/len(realLexicon)
lf = 2*lr*lp/(lr+lp)

print(f"P {round(100*precision,2)} R {round(100*recall,2)} F {round(100*f,2)} BP {round(100*bp,2)} BR {round(100*br,2)} BF {round(100*bf,2)} LP {round(100*lp,2)} LR {round(100*lr,2)} LF {round(100*lf,2)}")


#import matplotlib.pyplot as plt
#import seaborn as sns
#from sklearn import metrics
#
#cm = metrics.confusion_matrix(y_test, predictions)
#print(cm)



#print([x-y if x is not None and y is not None else None for x,y in zip(future_surprisal_without, future_surprisal_with)])

##      print(train[batch*args.batchSize:(batch+1)*args.batchSize])
#      numeric = [([0] + [stoi[data[x]]+1 for x in range(b, b+args.sequence_length) if x < len(data)]) for b in train[batch*args.batchSize:(batch+1)*batchSize]]
#     # print(numeric)
#      input_tensor = Variable(torch.LongTensor(numeric[:-1]).transpose(0,1).cuda(), requires_grad=False)
#      target_tensor = Variable(torch.LongTensor(numeric[1:]).transpose(0,1).cuda(), requires_grad=False)
#
#    #  print(char_embeddings)
#      embedded = char_embeddings(input_tensor)
#      out, _ = rnn(embedded, None)
#      logits = output(out) 
#      log_probs = logsoftmax(logits)
#   #   print(logits)
#  #    print(log_probs)
# #     print(target_tensor)
#      loss = train_loss(log_probs.view(-1, len(itos)+1), target_tensor.view(-1))
#      optim.zero_grad()
#      if batch % 10 == 0:
#         print(loss)
#      loss.backward()
#      optim.step()
#      
#

