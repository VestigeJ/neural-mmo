from pdb import set_trace as T

import os

from forge.blade import lib
#from forge.blade.lib.log import BlobSummary

from forge.trinity.ascend import Ascend, runtime, waittime, Log
from forge.trinity.timed import Summary

class Trinity():
   def __init__(self, cluster, pantheon, god, sword, quill):
      '''Pantheon-God-Sword (Cluster-Server-Core) infra 

      Trinity is three layer distributed infra design pattern for generic, 
      persistent, and asynchronous computation at the Cluster, Server, and
      Core levels. It is built from three user-provided Ascend subclasses, 
      which specify behavior at each layer. Trinity takes advantage of 
      Ascend's builtin performance logging and does not interfere with pdb 
      breakpoint debugging in local mode.
     
      To use Trinity, implement Pantheon, God, and Sword as Ascend subclasses
      to specify Cluster, Server, and Core level execution. Overriding the 
      step() function allows you to perform arbitrary computation and return 
      arbitrary data to the previous layer. Calling super.step() allows you 
      to send and receive arbitrary data to and from the next layer.

      Args:
         pantheon : A subclassed Pantheon class reference
         god      : A subclassed God class reference
         sword    : A subclassed Sword class reference
 
      Notes:
         Ascend is the base API defining distributed infra layers. Trinity is 
         simply three stacked Ascend layers. Ascend and Trinity are not 
         specific computation models: they are design patterns for creating
         computation models. You can implement anything from MPI 
         broadcast-reduce to OpenAI's Rapid to our  MMO style communications
         using Ascend + Trinity with relatively little code and testing.
      '''
      self.cluster  = cluster
      self.quill    = quill

      self.pantheon = pantheon
      self.god      = god
      self.sword    = sword

   def init(self, config, args, policy):
      '''
      Instantiates a Pantheon object to make Trinity runnable. Separated
      from __init__ to make Trinity usable as a stuct to hold Pantheon, 
      God, and Sword subclass references

      Args:
         config : A forge.blade.core.Config object
         args   : Additional command line arguments

      Returns:
         self: A self reference
      '''
      lib.ray.init(config, args.ray)
      self.config   = config

      #Logging and cluster management
      self.quill    = self.quill.remote(config)
      self.cluster  = self.cluster.remote(config, policy)

      ###Remote trinity workers
      self.pantheon = Ascend.init(
            self.pantheon,
            config,
            config.NPANTHEON)
      self.god = Ascend.init(
            self.god,
            config,
            config.NGOD)
      self.sword = Ascend.init(
            self.sword,
            config,
            config.NSWORD)

      #Sync model to rollout workers
      workers = [self.cluster]
      self.quill.init.remote(self)
      workers += self.pantheon + self.god + self.sword

      for w in workers:
         w.run.remote(self) 

      #Ascend.step(self.pantheon) # -> optimize model
      #Ascend.step(self.god)      # -> communicate obs to Sword
      #Ascend.step(self.sword)    # -> sync experience to Pantheon
   
      return self

   def step(self):
      '''Performs one cluster step which trains for one epoch

      Returns:
         txt: Logging string
      '''
      #blobs = BlobSummary().add(blobs)                                        
      #Update/checkpoint model and write logs                                 
      #stats, lifetime = self.quill.scrawl(blobs)  

      cluster          = self.pantheon[0]
      save, stats, log = cluster.step()

      log   = Log.summary([cluster.discipleLogs(), 
            *log, cluster.logs()])
      log   = str(Summary(log))

      #Write stats to txt file
      path = os.path.join(self.config.MODELDIR, self.config.STAT_FILE)
      txt = '\n'.join([save, stats, log])
      with open(path, 'a') as f:
         f.write(txt + '\n')

      return txt
