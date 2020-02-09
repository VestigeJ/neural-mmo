from pdb import set_trace as T
from copy import deepcopy

import ray
import ray.experimental.signal as signal

from forge.trinity.ascend import Ascend, runtime, waittime

from forge.ethyr.experience import RolloutManager
from forge.ethyr.torch.param import setParameters

import projekt

@ray.remote
class Sword(Ascend):
   '''Client level infrastructure demo

   This environment server runs a subset of the
   agents associated with a single server and
   computes model updates over collected rollouts

   At small scale, each server is collocated with a
   single client on the same CPU core. For larger
   experiments with multiple clients, decorate this
   class with @ray.remote to enable sharding.'''

   def __init__(self, config, idx):
      '''Initializes a model and relevent utilities
                                                                              
      Args:                                                                   
         trinity : A Trinity object as shown in __main__                      
         config  : A Config object as shown in __main__                       
         idx     : Unused hardware index                                      
      '''
      super().__init__(config, idx)
      config        = deepcopy(config)
      device        = config.DEVICE
      self.config   = config 

      self.net      = projekt.Policy(config).to(device).eval()

   def recvModel(self, timeout=0):
      #Receive weight packets
      packet = Ascend.recv('Model', [self.trinity.cluster], timeout)

      #Sync model weights; batch obs; compute forward pass
      if packet is not None:
         setParameters(self.net, packet[-1])

   def run(self, trinity):                                                    
      self.trinity = trinity
      self.recvModel(timeout=None)

   @waittime
   def sync(self, packet):
      Ascend.send('Experience', packet)

   @runtime
   def step(self, packet):
      '''Synchronizes weights from upstream; computes
      agent decisions; computes policy updates.
                                                                              
      Args:                                                                   
         packet   : An IO object specifying observations
         weights  : An optional parameter vector to replace model weights
         backward : (bool) Whether of not a backward pass should be performed  
      Returns:                                                                   
         data    : The same IO object populated with action decisions
         grads   : A vector of gradients aggregated across trajectories
         summary : A BlobSummary object logging agent statistics
      '''   
      #Compute forward pass
      self.net(packet, None)

      #Send experience and logs
      self.sync(packet)

      Ascend.send('Utilization', self.logs())

      return packet

