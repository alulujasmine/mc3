#! /usr/bin/env python

# ******************************* START LICENSE *****************************
# 
# Multi-Core Markov-chain Monte Carlo (MC3), a code to estimate
# model-parameter best-fitting values and Bayesian posterior
# distributions.
# 
# This project was completed with the support of the NASA Planetary
# Atmospheres Program, grant NNX12AI69G, held by Principal Investigator
# Joseph Harrington.  Principal developers included graduate student
# Patricio E. Cubillos and programmer Madison Stemm.  Statistical advice
# came from Thomas J. Loredo and Nate B. Lust.
# 
# Copyright (C) 2014 University of Central Florida.  All rights reserved.
# 
# This is a test version only, and may not be redistributed to any third
# party.  Please refer such requests to us.  This program is distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.
# 
# Our intent is to release this software under an open-source,
# reproducible-research license, once the code is mature and the first
# research paper describing the code has been accepted for publication
# in a peer-reviewed journal.  We are committed to development in the
# open, and have posted this code on github.com so that others can test
# it and give us feedback.  However, until its first publication and
# first stable release, we do not permit others to redistribute the code
# in either original or modified form, nor to publish work based in
# whole or in part on the output of this code.  By downloading, running,
# or modifying this code, you agree to these conditions.  We do
# encourage sharing any modifications with us and discussing them
# openly.
# 
# We welcome your feedback, but do not guarantee support.  Please send
# feedback or inquiries to:
# 
# Joseph Harrington <jh@physics.ucf.edu>
# Patricio Cubillos <pcubillos@fulbrightmail.org>
# 
# or alternatively,
# 
# Joseph Harrington and Patricio Cubillos
# UCF PSB 441
# 4111 Libra Drive
# Orlando, FL 32816-2385
# USA
# 
# Thank you for using MC3!
# ******************************* END LICENSE *******************************

import os, sys, warnings, time
import argparse, ConfigParser
import numpy as np
import multiprocessing as mpr

sys.path.append(os.path.dirname(os.path.realpath(__file__))+'/cfuncs/lib')
import chain    as ch
import gelman_rubin as gr
import modelfit as mf
import mcutils  as mu
import mcplots  as mp
import timeavg  as ta

def mcmc(data,         uncert=None,      func=None,     indparams=[],
         params=None,  pmin=None,        pmax=None,     stepsize=None,
         prior=None,   priorlow=None,    priorup=None,
         numit=10,     nchains=10,       walk='demc',   wlike=False,
         leastsq=True, chisqscale=False, grtest=True,   burnin=0,
         thinning=1,   plots=False,      savefile=None, savemodel=None,
         comm=None,    resume=False):
  """
  This beautiful piece of code runs a Markov-chain Monte Carlo algoritm.

  Parameters:
  -----------
  data: 1D ndarray
     Dependent data fitted by func.
  uncert: 1D ndarray
     Uncertainty of data.
  func: callable or string-iterable
     The callable function that models data as:
        model = func(params, *indparams)
     Or an iterable (list, tuple, or ndarray) of 3 strings:
        (funcname, modulename, path)
     that specify the function name, function module, and module path.
     If the module is already in the python-path scope, path can be omitted.
  indparams: tuple
     Additional arguments required by func.
  params: 1D or 2D ndarray
     Set of initial fitting parameters for func.  If 2D, of shape
     (nparams, nchains), it is assumed that it is one set for each chain.
  pmin: 1D ndarray
     Lower boundaries of the posteriors.
  pmax: 1D ndarray
     Upper boundaries of the posteriors.
  stepsize: 1D ndarray
     Proposal jump scale.  If a values is 0, keep the parameter fixed.
     Negative values indicate a shared parameter (See Note 1).
  prior: 1D ndarray
     Parameter prior distribution means (See Note 2).
  priorlow: 1D ndarray
     Lower prior uncertainty values (See Note 2).
  priorup: 1D ndarray
     Upper prior uncertainty values (See Note 2).
  numit: Scalar
     Total number of iterations.
  nchains: Scalar
     Number of simultaneous chains to run.
  walk: String
     Random walk algorithm:
     - 'mrw':  Metropolis random walk.
     - 'demc': Differential Evolution Markov chain.
  wlike: Boolean
     If True, calculate the likelihood in a wavelet-base.  This requires
     three additional parameters (See Note 3).
  leastsq: Boolean
     Perform a least-square minimization before the MCMC run.
  chisqscale: Boolean
     Scale the data uncertainties such that the reduced chi-squared = 1.
  grtest: Boolean
     Run Gelman & Rubin test.
  burnin: Scalar
     Burned-in (discarded) number of iterations at the beginning
     of the chains.
  thinning: Integer
     Thinning factor of the chains (use every thinning-th iteration) used
     in the GR test and plots.
  plots: Boolean
     If True plot parameter traces, pairwise-posteriors, and posterior
     histograms.
  savefile: String
     If not None, filename to store allparams (with np.save).
  savemodel: String
     If not None, filename to store the values of the evaluated function
     (with np.save).
  resume: Boolean
     If True resume a previous run.

  Returns:
  --------
  allparams: 2D ndarray
     An array of shape (nfree, numit-nchains*burnin) with the MCMC
     posterior distribution of the fitting parameters.
  bestp: 1D ndarray
     Array of the best fitting parameters.

  Notes:
  ------
  1.- To set one parameter equal to another, set its stepsize to the
      negative index in params (Starting the count from 1); e.g.: to set
      the second parameter equal to the first one, do: stepsize[1] = -1.
  2.- If any of the fitting parameters has a prior estimate, e.g.,
        param[i] = p0 +up/-low,
      with up and low the 1sigma uncertainties.  This information can be
      considered in the MCMC run by setting:
      prior[i]    = p0
      priorup[i]  = up
      priorlow[i] = low
      All three: prior, priorup, and priorlow must be set and, furthermore,
      priorup and priorlow must be > 0 to be considered as prior.
  3.- FINDME WAVELET LIKELIHOOD

  Examples:
  ---------
  >>> # See examples: https://github.com/pcubillos/MCcubed/tree/master/examples

  Developers:
  -----------
  Kevin Stevenson    UCF  kevin218@knights.ucf.edu
  Patricio Cubillos  UCF  pcubillos@fulbrightmail.org

  Modification History:
  ---------------------
    2008-05-02  kevin     Initial implementation
    2008-06-21  kevin     Finished updating
    2009-11-01  kevin     Updated for multi events:
    2010-06-09  kevin     Updated for ipspline, nnint & bilinint
    2011-07-06  kevin     Updated for Gelman-Rubin statistic
    2011-07-22  kevin     Added principal component analysis
    2011-10-11  kevin     Added priors
    2012-09-03  patricio  Added Differential Evolution MC. Documented.
    2013-01-31  patricio  Modified for general purposes.
    2013-02-21  patricio  Added support distribution for DEMC.
    2014-03-31  patricio  Modified to be completely agnostic of the
                          fitting function, updated documentation.
    2014-04-17  patricio  Revamped use of 'func': no longer requires a
                          wrapper.  Alternatively, can take a string list with
                          the function, module, and path names.
    2014-04-19  patricio  Added savefile, thinning, plots, and mpi arguments.
    2014-05-04  patricio  Added Summary print out.
    2014-05-09  patricio  Added Wavelet-likelihood calculation.
    2014-05-09  patricio  Changed figure types from pdf to png, because it's
                          much faster.
    2014-05-26  patricio  Changed mpi bool argument by comm.  Re-engineered
                          MPI communications to make direct calls to func.
    2014-06-09  patricio  Fixed glitch with leastsq+informative priors.
    2014-10-17  patricio  Added savemodel argument.
    2014-10-23  patricio  Added support for func hack.
    2015-02-04  patricio  Added resume argument.
    2015-04-19  patricio  Replaced MPI with multiprocessing.
  """
  # Import the model function:
  if type(func) in [list, tuple, np.ndarray]:
    if func[0] != 'hack':
      if len(func) == 3:
        sys.path.append(func[2])
      exec('from %s import %s as func'%(func[1], func[0]))
  elif not callable(func):
    mu.exit(message="'func' must be either, a callable, or an iterable (list, "
            "tuple, or ndarray) of strings with the model function, file, "
            "and path names.")

  nproc = nchains
  if np.ndim(params) == 1:  # Force it to be 2D (one for each chain)
    params  = np.atleast_2d(params)
  nparams = len(params[0])  # Number of model params
  ndata   = len(data)       # Number of data values
  # Set default uncertainties:
  if uncert is None:
    uncert = np.ones(ndata)
  # Set default boundaries:
  if pmin is None:
    pmin = np.zeros(nparams) - np.inf
  if pmax is None:
    pmax = np.zeros(nparams) + np.inf
  # Set default stepsize:
  if stepsize is None:
    stepsize = 0.1 * np.abs(params[0])
  # Set prior parameter indices:
  if (prior is None) or (priorup is None) or (priorlow is None):
    prior   = priorup = priorlow = np.zeros(nparams)  # Zero arrays
  iprior = np.where(priorlow != 0)[0]
  ilog   = np.where(priorlow <  0)[0]

  nfree    = np.sum(stepsize > 0)        # Number of free parameters
  chainlen = int(np.ceil(numit/nchains)) # Number of iterations per chain
  ifree    = np.where(stepsize > 0)[0]   # Free   parameter indices
  ishare   = np.where(stepsize < 0)[0]   # Shared parameter indices
  # Number of model parameters (excluding wavelet parameters):
  if wlike:
    mpars  = nparams - 3
  else:
    mpars  = nparams

  # Intermediate steps to run GR test and print progress report:
  intsteps   = chainlen / 10

  # Allocate arrays with variables:
  numaccept  = np.zeros(nchains)          # Number of accepted proposal jumps
  outbounds  = np.zeros((nchains, nfree), np.int)   # Out of bounds proposals
  allparams  = np.zeros((nchains, nfree, chainlen)) # Parameter's record
  if savemodel is not None:
    allmodel = np.zeros((nchains, ndata, chainlen)) # Fit model

  if resume:
    oldparams = np.load(savefile)
    nold = np.shape(oldparams)[2] # Number of old-run iterations
    allparams = np.dstack((oldparams, allparams))
    if savemodel is not None:
      allmodel  = np.dstack((np.load(savemodel), allmodel))
    # Set params to the last-iteration state of the previous run:
    params = np.repeat(params, nchains, 0)
    params[:,ifree] = oldparams[:,:,-1]
  else:
    nold = 0

  # DEMC parameters:
  gamma  = 2.4 / np.sqrt(2*nfree)
  gamma2 = 0.001  # Jump scale factor of support distribution

  # Least-squares minimization:
  if leastsq:
    fitargs = (params[0], func, data, uncert, indparams, stepsize, pmin, pmax,
               prior, priorlow, priorup)
    fitchisq, dummy = mf.modelfit(params[0,ifree], args=fitargs)
    fitbestp = np.copy(params[0, ifree])
    print("Least-squares best fitting parameters: \n%s\n"%str(fitbestp))

  # Replicate to make one set for each chain: (nchains, nparams):
  if np.shape(params)[0] != nchains:
    params = np.repeat(params, nchains, 0)
    # Start chains with an initial jump:
    for p in ifree:
      # For each free param, use a normal distribution: 
      params[1:, p] = np.random.normal(params[0, p], stepsize[p], nchains-1)
      # Stay within pmin and pmax boundaries:
      params[np.where(params[:, p] < pmin[p]), p] = pmin[p]
      params[np.where(params[:, p] > pmax[p]), p] = pmax[p]
  
  # Update shared parameters:
  for s in ishare:
    params[:, s] = params[:, -int(stepsize[s])-1]

  # Calculate chi-squared for model using current params:
  models = np.zeros((nchains, ndata))
  # FINDME: think what to do with this.

  # Set up Chain Processes:
  qpars  = mpr.Queue()  # Parameters Queue
  qchisq = mpr.Queue()  # Chi-square Queue
  timeout = 10.0         # FINDME: set as option
  chainsize = np.zeros(nchains, np.int)  # Current length of each chain 

  # Launch Chains:
  for i in np.arange(nproc):
    ch.Chain(func, indparams, qpars, qchisq, data, uncert,
              wlike, prior, priorlow, priorup, 1.0, timeout=timeout)

  # Evaluate first round of models:
  for i in np.arange(nchains):
    qpars.put([i, params[i]])  # Send a tuple: [chainID, fitting parameters]

  # Receive chi-square:
  chisq = np.zeros(nchains)
  for i in np.arange(nchains):
    ID, result = qchisq.get(timeout=timeout)  # Receive [chainID, chisq]
    chisq[ID] = result
    chainsize[ID] += 1

  # Scale data-uncertainties such that reduced chisq = 1:
  if chisqscale:
    chifactor = np.sqrt(np.amin(chisq)/(ndata-nfree))

    for i in np.arange(nproc):
      # FINDME: Send chifactor to each chain:
      #uncert *= chifactor
      pass

    # Re-calculate chisq with the new uncertainties:
    for c in np.arange(nchains):
      qpars.put([i, params[i]])
    for i in np.arange(nchains):
      ID, result = qout.get(timeout=timeout)
      chisq[ID] = result

    if leastsq:
      fitchisq = np.copy(chisq[0])

  # Get lowest chi-square and best fitting parameters:
  bestchisq = np.amin(chisq)
  bestp     = np.copy(params[np.argmin(chisq)])
  #bestmodel = np.copy(models[np.argmin(chisq)])

  # FINDME: do something with models
  if savemodel is not None:
    allmodel[:,:,0] = models

  # Set up the random walks:
  if   walk == "mrw":
    # Generate proposal jumps from Normal Distribution for MRW:
    mstep   = np.random.normal(0, stepsize[ifree], (chainlen, nchains, nfree))
  elif walk == "demc":
    # Support random distribution:
    support = np.random.normal(0, stepsize[ifree], (chainlen, nchains, nfree))
    # Generate indices for the chains such r[c] != c:
    r1 = np.random.randint(0, nchains-1, (nchains, chainlen))
    r2 = np.random.randint(0, nchains-1, (nchains, chainlen))
    for c in np.arange(nchains):
      r1[c][np.where(r1[c]==c)] = nchains-1
      r2[c][np.where(r2[c]==c)] = nchains-1

  # Uniform random distribution for the Metropolis acceptance rule:
  unif = np.random.uniform(0, 1, (chainlen, nchains))

  # Proposed iteration parameters and chi-square (per chain):
  nextp     = np.copy(params)    # Proposed parameters
  nextchisq = np.zeros(nchains)  # Chi square of nextp 

  # Start loop:
  print("Start MCMC chains  ({:s})".format(time.ctime()))
  for i in np.arange(chainlen):
    # Proposal jump:
    if   walk == "mrw":
      jump = mstep[i]
    elif walk == "demc":
      jump = (gamma  * (params[r1[:,i]]-params[r2[:,i]])[:,ifree] +
              gamma2 * support[i]                                 )
    # Propose next point:
    nextp[:,ifree] = params[:,ifree] + jump

    # Check it's within boundaries: 
    outpars = np.asarray(((nextp < pmin) | (nextp > pmax))[:,ifree])
    outflag  = np.any(outpars, axis=1)
    outbounds += ((nextp < pmin) | (nextp > pmax))[:,ifree]
    for p in ifree:
      nextp[np.where(nextp[:, p] < pmin[p]), p] = pmin[p]
      nextp[np.where(nextp[:, p] > pmax[p]), p] = pmax[p]

    # Update shared parameters:
    for s in ishare:
      nextp[:, s] = nextp[:, -int(stepsize[s])-1]

    # Evaluate the next round of models:
    for j in np.arange(nchains):
    #for j in np.where(~outflag)[0]:
      qpars.put([j, nextp[j]])
  
    # Receive chi-square:
    for j in np.arange(nchains):
    #for j in np.where(~outflag)[0]:
      ID, result = qchisq.get(timeout=timeout)
      nextchisq[ID] = result
      chainsize[ID] += 1

    # Reject out-of-bound jumps:
    nextchisq[np.where(outflag)] = np.inf

    # Evaluate which steps are accepted and update values:
    accept = np.exp(0.5 * (chisq - nextchisq))
    accepted = accept >= unif[i]
    if i >= burnin:
      numaccept += accepted
    # Update params and chi square:
    params[accepted] = nextp    [accepted]
    chisq [accepted] = nextchisq[accepted]

    # Check lowest chi-square:
    if np.amin(chisq) < bestchisq:
      bestp = np.copy(params[np.argmin(chisq)])
      bestchisq = np.amin(chisq)

    # Store current iteration values:
    allparams[:,:,i+nold] = params[:, ifree]
    # FINDME:
    if savemodel is not None:
      models[~accepted] = allmodel[~accepted,:,i+nold-1]
      allmodel[:,:,i+nold] = models
  
    # Print intermediate info:
    if ((i+1) % intsteps == 0) and (i > 0):
      mu.progressbar((i+1.0)/chainlen)
      print("Out-of-bound Trials: ")
      print(np.sum(outbounds, axis=0))
      print("Best Parameters:   (chisq=%.4f)\n%s"%(bestchisq, str(bestp)))

      # Gelman-Rubin statistic:
      if grtest and (i+nold) > burnin:
        psrf = gr.convergetest(allparams[:, :, burnin:i+nold+1:thinning])
        print("Gelman-Rubin statistic for free parameters:\n" + str(psrf))
        if np.all(psrf < 1.01):
          print("All parameters have converged to within 1% of unity.")
      # Save current results:
      if savefile is not None:
        np.save(savefile, allparams[:,:,0:i+nold])
      if savemodel is not None:
        np.save(savemodel, allmodel[:,:,0:i+nold])

  # Stack together the chains:
  allstack = allparams[0, :, burnin:]
  for c in np.arange(1, nchains):
    allstack = np.hstack((allstack, allparams[c, :, burnin:]))
  # And the models:
  if savemodel is not None:
    modelstack = allmodel[0,:,burnin:]
    for c in np.arange(1, nchains):
      modelstack = np.hstack((modelstack, allmodel[c, :, burnin:]))

  # Print out Summary:
  print("\nFin, MCMC Summary:\n"
          "------------------")
  # Evaluate model for best fitting parameters:
  fargs = [bestp] + indparams
  bestmodel = func(*fargs)

  # Get some stats:
  nsample   = (chainlen-burnin)*nchains # This sample
  ntotal    = (nold+chainlen-burnin)*nchains
  BIC       = bestchisq + nfree*np.log(ndata)
  redchisq  = bestchisq/(ndata-nfree)
  sdr       = np.std(bestmodel-data)

  fmtlen = len(str(ntotal))
  print(" Burned in iterations per chain: {:{}d}".format(burnin,   fmtlen))
  print(" Number of iterations per chain: {:{}d}".format(chainlen, fmtlen))
  print(" MCMC sample size:               {:{}d}".format(nsample,  fmtlen))
  if resume:
    print(" Total MCMC sample size:         {:{}d}".format(ntotal, fmtlen))
  print(" Acceptance rate:   %.2f%%\n"%(np.sum(numaccept)*100.0/nsample))

  meanp   = np.mean(allstack, axis=1) # Parameters mean
  uncertp = np.std(allstack,  axis=1) # Parameter standard deviation
  print(" Best-fit params    Uncertainties   Signal/Noise       Sample Mean")
  for i in np.arange(nfree):
    print(" {: 15.7e}  {: 15.7e}   {:12.2f}   {: 15.7e}".format(bestp[ifree][i],
           uncertp[i], np.abs(bestp[ifree][i])/uncertp[i], meanp[i]))

  if leastsq and np.any(np.abs((bestp[ifree]-fitbestp)/fitbestp) > 1e-08):
    np.set_printoptions(precision=8)
    print("\n *** MCMC found a better fit than the minimizer ***\n"
            " MCMC best-fitting parameters:        (chisq={:.8g})\n {:s}\n"
            " Minimizer best-fitting parameters:   (chisq={:.8g})\n"
            " {:s}".format(bestchisq, str(bestp[ifree]), 
                           fitchisq,  str(fitbestp)))

  fmtl = len("%.4f"%BIC)  # Length of string formatting
  print("")
  if chisqscale:
    print(" sqrt(reduced chi-squared) factor: {:{}.4f}".format(chifactor, fmtl))
  print(  " Best-parameter's chi-squared:     {:{}.4f}".format(bestchisq, fmtl))
  print(  " Bayesian Information Criterion:   {:{}.4f}".format(BIC,       fmtl))
  print(  " Reduced chi-squared:              {:{}.4f}".format(redchisq,  fmtl))
  print(  " Standard deviation of residuals:  {:.6g}\n".format(sdr))

  if plots:
    print("Plotting figures ...")
    # Extract filename from savefile:
    if savefile is not None:
      if savefile.rfind(".") == -1:
        fname = savefile[savefile.rfind("/")+1:] # Cut out file extention.
      else:
        fname = savefile[savefile.rfind("/")+1:savefile.rfind(".")]
    else:
      fname = "MCMC"
    # Trace plot:
    mp.trace(allstack,     thinning=thinning, savefile=fname+"_trace.png")
    # Pairwise posteriors:
    mp.pairwise(allstack,  thinning=thinning, savefile=fname+"_pairwise.png")
    # Histograms:
    mp.histogram(allstack, thinning=thinning, savefile=fname+"_posterior.png")
    # RMS vs bin size:
    rms, rmse, stderr, bs = ta.binrms(bestmodel-data)
    mp.RMS(bs, rms, stderr, rmse, binstep=len(bs)/500+1,
                                              savefile=fname+"_RMS.png")
    if indparams != [] and np.size(indparams[0]) == ndata:
      mp.modelfit(data, uncert, indparams[0], bestmodel,
                                              savefile=fname+"_model.png")

  # Save definitive results:
  if savefile is not None:
    np.save(savefile,  allparams)
  if savemodel is not None:
    np.save(savemodel, allmodel)

  return allstack, bestp
