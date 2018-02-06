import sys, os
import numpy as np
import string

import cPickle as pickle

from basic.constant import ROOT_PATH
from basic.common import niceNumber,printStatus, writeRankingResults
from basic.annotationtable import readConcepts,readAnnotationsFrom
from basic.metric import getScorer
from basic.util import readImageSet


INFO = __file__


def process(options, collection, annotationName, runfile):
  rootpath = options.rootpath
  
  p1_scorer = getScorer('P@1')
  p3_scorer = getScorer('P@3')
  r1_scorer = getScorer('R@1')
  r3_scorer = getScorer('R@3')
  ndcg1_scorer = getScorer('NDCG2@1')
  ndcg3_scorer = getScorer('NDCG2@3')
  ap_scorer = getScorer('AP')
  rr_scorer = getScorer('RR')

  datafiles = [x.strip() for x in open(runfile).readlines() if x.strip() and not x.strip().startswith('#')]
  nr_of_runs = len(datafiles)
  
  concepts = readConcepts(collection, annotationName, rootpath=rootpath)  
  nr_of_concepts = len(concepts)
  
  name2label = [{} for i in range(nr_of_concepts)]
  rel_conset = {}
  
  for i in range(nr_of_concepts):
    names,labels = readAnnotationsFrom(collection, annotationName, concepts[i], skip_0=False, rootpath=rootpath)
    #names = map(int, names)
    name2label[i] = dict(zip(names,labels))

    for im,lab in zip(names,labels):
      if lab > 0:
        rel_conset.setdefault(im,set()).add(i)

  # ('7975436322', set([33]))
  # for im, im_labels in rel_conset.items():
  #   print(im, im_labels)

  for run_idx in range(nr_of_runs):
    data = pickle.load(open(datafiles[run_idx],'rb'))
    scores = data['scores']
    assert(scores.shape[1] == nr_of_concepts)
    imset = data['id_images']
    # for im in imset:
    #     print(im)
    #     raw_input()
    nr_of_images = len(imset)
    #print datafiles[run_idx], imset[:5], imset[-5:]

    res = np.zeros((nr_of_images, 8))
    for j in range(nr_of_images):
      ranklist = zip(range(nr_of_concepts), scores[j,:])
      ranklist.sort(key=lambda v:v[1], reverse=True)
      # print(ranklist)
      # raw_input()
      rel_set = rel_conset.get(imset[j], set())
      sorted_labels = [int(x[0] in rel_set) for x in ranklist]
      # print(sorted_labels)
      # raw_input()
      assert len(sorted_labels) == nr_of_concepts
      p1 = p1_scorer.score(sorted_labels)
      p3 = p3_scorer.score(sorted_labels)
      r1 = r1_scorer.score(sorted_labels)
      r3 = r3_scorer.score(sorted_labels)
      ndcg1 = ndcg1_scorer.score(sorted_labels)
      ndcg3 = ndcg3_scorer.score(sorted_labels)
      ap = ap_scorer.score(sorted_labels)
      rr = rr_scorer.score(sorted_labels)

      res[j,:] = [p1, p3, r1, r3, ndcg1, ndcg3, ap, rr]
    avg_perf = res.mean(axis=0)
    print '{}\t{}'.format(
      os.path.split(datafiles[run_idx])[-1],
      ' & '.join(['%.4f' % x for x in avg_perf])
    )

def main(argv=None):
  if argv is None:
    argv = sys.argv[1:]

  from optparse import OptionParser
  parser = OptionParser(usage="""usage: %prog [options] collection annotationName runfile""")
  parser.add_option("--rootpath", default=ROOT_PATH, type="string", help="rootpath (default: %s)" % ROOT_PATH)

  (options, args) = parser.parse_args(argv)
  if len(args) < 3:
    parser.print_help()
    return 1

  return process(options, args[0], args[1], args[2])

if __name__ == "__main__":
  sys.exit(main())



