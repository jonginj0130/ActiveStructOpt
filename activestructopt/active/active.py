from activestructopt.optimization.basinhopping.basinhopping import basinhop
from activestructopt.gnn.ensemble import Ensemble
from activestructopt.dataset.dataset import make_data_splits, update_datasets
import numpy as np
import gc
import torch
import torch.multiprocessing as mp

def active_learning(
    optfunc, 
    args, 
    target,
    config, 
    initial_structure, 
    max_forward_calls = 100,
    N = 30, 
    k = 5, 
    perturbrmin = 0.0, 
    perturbrmax = 1.0, 
    split = 1/3, 
    device = 'cuda',
    bh_starts = 100,
    bh_iters_per_start = 100,
    bh_lr = 0.01,
    bh_step_size = 0.1,
    bh_σ = 0.0025,
    print_mses = True,
    ):
  mp.set_start_method('spawn', force = True)
  pool = mp.Pool(2)
  structures, ys, datasets, kfolds, test_indices, test_data, test_targets = make_data_splits(
    initial_structure,
    optfunc,
    args,
    config['dataset'],
    N = N,
    k = k,
    perturbrmin = perturbrmin,
    perturbrmax = perturbrmax,
    split = split,
    device = device,
  )
  mses = [np.mean((y - target) ** 2) for y in ys]
  if print_mses:
    print(mses)
  active_steps = max_forward_calls - N
  for i in range(active_steps):
    starting_structure = structures[np.argmin(mses)].copy()
    ensemble = Ensemble(k, config, datasets, pool)
    ensemble.train()
    ensemble.set_scalar_calibration(test_data, test_targets)
    new_structure = basinhop(ensemble, starting_structure, target, 
      config['dataset'], nhops = bh_starts, niters = bh_iters_per_start, 
      λ = 0.0 if i == (active_steps - 1) else 1.0, lr = bh_lr, 
      step_size = bh_step_size, rmcσ = bh_σ)
    structures.append(new_structure)
    datasets, y = update_datasets(
      datasets,
      new_structure,
      config['dataset'],
      optfunc,
      args,
      device,
    )
    ys.append(y)
    new_mse = np.mean((y - target) ** 2)
    mses.append(new_mse)
    if print_mses:
      print(new_mse)
    gc.collect()
    torch.cuda.empty_cache()
  return structures, ys, mses, (
      datasets, kfolds, test_indices, test_data, test_targets, ensemble)
