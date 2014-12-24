'''
Module for ROM models that require specific sampling sets, e.g. Stochastic Collocation
'''
#for future compatibility with Python 3--------------------------------------------------------------
from __future__ import division, print_function, unicode_literals, absolute_import
import warnings
warnings.simplefilter('default',DeprecationWarning)
#End compatibility block for Python 3----------------------------------------------------------------

#External Modules------------------------------------------------------------------------------------
import os
import copy
import shutil
import numpy as np
from utils import metaclass_insert, returnPrintTag, returnPrintPostTag
import abc
import importlib
from operator import mul
from functools import reduce
#External Modules End--------------------------------------------------------------------------------

#Internal Modules------------------------------------------------------------------------------------
from BaseClasses import BaseType, Assembler
import PostProcessors #import returnFilterInterface
import Samplers
import Models

import IndexSets
import Quadratures
import OrthoPolynomials

from CustomCommandExecuter import execCommand
#Internal Modules End--------------------------------------------------------------------------------

class SamplingModel(Models.Dummy,Samplers.Grid):
  def __init__(self):
    Samplers.Grid.__init__(self)
    Models.Dummy.__init__(self)
    self.type = 'SamplingROM'

  def initialize(self,*args,**kwargs):
    #Samplers.Grid.initialize(self,*args,**kwargs)
    #Models.Dummy.initialize(self,*args,**kwargs)
    try: Samplers.Grid.initialize(self,*args,**kwargs)
    except TypeError: Models.Dummy.initialize(self,*args,**kwargs)

  def localInputAndChecks(self,xmlNode):
    Samplers.Grid.localInputAndChecks(self,xmlNode)

class StochasticPolynomials(SamplingModel):
  def __init__(self):
    SamplingModel.__init__(self)
    self.type = 'StochasticPolynomials'
    self.printTag    = returnPrintTag('SAMPLING ROM STOCHASTIC POLYS')
    self.maxPolyOrder= None  #L, the maximum polynomial expansion order to use
    self.indexSetType= None  #TP, TD, or HC; the type of index set to use
    self.adaptive    = False #not yet implemented; adaptively samples index set and/or quadrature

  def _readMoreXML(self,xmlNode):
    Samplers.Sampler._readMoreXML(self,xmlNode)

  def localInputAndChecks(self,xmlNode):
    # sampling side #
    self.indexSetType =     xmlNode.attrib['indexSetType']  if 'indexSetType' in xmlNode.attrib.keys() else 'Tensor Product'
    self.maxPolyOrder = int(xmlNode.attrib['maxPolyOrder']) if 'maxPolyOrder' in xmlNode.attrib.keys() else 2
    #FIXME add AdaptiveSP # self.adaptive     =(1 if xmlNode.attrib['adaptive'].lower() in ['true','t','1','y','yes'] else 0) if 'adaptive' in xmlNode.attrib.keys() else 0
    for child in xmlNode:
      importanceWeight = float(child.attrib['impWeight']) if 'impWeight' in child.attrib.keys() else 1
      if child.tag=='Distribution':
        varName = '<distribution>'+child.attrib['name']
      elif child.tag == 'variable':
        varName = child.attrib['name']
      self.axisName.append(varName) #TODO maybe gridInfo.keys() is the same as axisName?
      quad_find = xmlNode.find('quadrature')
      if quad_find != None:
        quadType = quad_find.find('type').text if quad_find.find('type') != None else 'DEFAULT'
        polyType = quad_find.find('polynomials').text if quad_find.find('polynomials') != None else 'DEFAULT'
      else:
        quadType = 'DEFAULT'
        polyType = 'DEFAULT'
      print("DEBUG quad type for "+varName+" is "+quadType,polyType)
      self.gridInfo[varName] = [quadType,polyType,importanceWeight]
    SamplingModel.localInputAndChecks(self,xmlNode)

    # ROM side #


  def localInitialize(self):
    Samplers.Grid.localInitialize(self)
    for varName,dat in self.gridInfo.items():
      #FIXME alpha,beta for laguerre, jacobi
      if dat[0] not in self.distDict[varName].compatibleQuadrature and dat[0]!='DEFAULT':
        raise IOError (self.printTag+' Incompatible quadrature <'+dat[0]+'> for distribution of '+varName+': '+distribution.type)
      if dat[0]=='DEFAULT': dat[0]=Quadratures.returnInstance(*self.distDict[varName].preferredQuadrature)
      else: quad = Quadratures.returnInstance(dat[0])
      quad.initialize() #take XMLnode as argument?
      self.quadDict[varName] = quad

      if dat[1]=='DEFAULT': dat[1] = self.distDict[varName].preferredPolynomials
      poly = OrthoPolynomials.returnInstance(dat[1])
      poly.initialize()
      self.polyDict[varName] = poly
      #TODO how to check compatible polys?  Polys compatible with quadrature more than distribution, kind of both

      self.importanceDict[varName] = dat[2]

      #self.distDict[varName].setQuadrature(quad)
      #self.distDict[varName].setPolynomials(poly,self.maxPolyOrder)
      #self.distDict[varName].setImportanceWeight(dat[2])
    self.norm = np.prod(list(d.probabilityNorm() for d in self.distDict.values()))

    self.indexSet = IndexSets.returnInstance(self.indexSetType)
    self.indexSet.initialize(self.distDict)

    self.sparseGrid = Quadratures.SparseQuad()
    self.sparseGrid.initialize(self.indexSet,self.maxPolyOrder,self.distDict,self.quadDict,self.polyDict)
    self.limit=len(self.sparseGrid)

  def localGenerateInput(self,model,myInput):
    pts,weight = self.sparseGrid[self.counter-1]
    for v,varName in enumerate(self.axisName):
      self.values[varName] = pts[v]
      self.inputInfo['SampledVarsPb'][varName] = self.distDict[varName].pdf(self.values[varName])
    self.inputInfo['PointProbability'] = reduce(mul,self.inputInfo['SampledVarsPb'].values())
    self.inputInfo['ProbabilityWeight'] = weight
    self.inputInfo['SamplerType'] = 'Sparse Grid (SamplingROM)'

  #TODO add a check for when "amIReady" is finished, to run the Model creation (coefficient and poly creator)


__base = "SamplingModel"

__interFaceDict = {}
__interFaceDict['StochasticPolynomials'] = StochasticPolynomials
__knownTypes = list(__interFaceDict.keys())

def knownTypes():
  return __knownTypes

def returnInstance(Type):
  try: return __interFaceDict[Type]()
  except KeyError: raise NameError('not known '+__base+'type '+Type)

Samplers.addKnownTypes(__interFaceDict)

