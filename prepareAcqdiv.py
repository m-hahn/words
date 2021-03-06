from config import ACQDIV_HOME



import os
import random
#import accessISWOCData
#import accessTOROTData
import sys
 

import csv


def readCSV(paths):
   result = []
   header = None
   assert len(paths) < 10
   paths = sorted(paths)
   print(paths)
   for path in paths:
      print(path)
      with open(path, "r") as inFile:
         data = csv.reader(inFile, delimiter=",", quotechar='"')
#         data = [x.split("\t") for x in inFile.read().strip().split("\n")]
 #        headerNew = data[0]
         if header is None:
            headerNew = next(data)
            header = headerNew
         for line in data:
             assert len(line) == len(header), (line, header)
             result.append(line)
         assert header == headerNew, (header, headerNew)
   return (header, result)

def printTSV(table, path):
   header, data = table
   with open(path, "w") as outFile:
       outFile.write("\t".join(header)+"\n")
       for line in data:
           outFile.write("\t".join(line)+"\n")

def mergeCSV(infiles, outfile):
   with open(outfile, "w") as outFile:
      for path in infiles:
          with open(path, "r") as inFile:
             outFile.write(inFile.read())


basePath = ACQDIV_HOME+"/csv/"
basePathOut = ACQDIV_HOME+"/tsv/"
names = ["speakers","morphemes",  "utterances", "words", "uniquespeakers"]


for name in names:
  infiles = [basePath+x for x in os.listdir(basePath) if x.startswith(name) and x.endswith(".csv")]
  if len(infiles) > 1:
    mergeCSV(infiles = infiles, outfile = basePath+name+".csv")
  dataset = readCSV([basePath+name+".csv"])
  printTSV(dataset, basePathOut+name+".tsv")


#reader = AcqdivReader("Japanese")



def find_child_lines(speakers_file):
        child_id=[]
        for line_ in speakers_file:
                if "Target_Child" in line_:
                        column=line_.split("\t")
                        if column[2] not in child_id:
                                child_id.append(column[2])
        return child_id


speakers_file=open( (basePathOut + "speakers.tsv"), "r")
list_=(find_child_lines(speakers_file))
speakers_file.close()

utterances_file=open((basePathOut + "utterances.tsv"), "r")
lines_=utterances_file.readlines()
utterances_file.close()


def remove_child_lines(utterances_file):
        for line_ in lines_:
                column=line_.split("\t")
                if column[3] not in list_:
                        utterances_file.write(line_)

utterances_file=open((basePathOut + "utterances.tsv"),"w")
remove_child_lines(utterances_file)
utterances_file.close()

