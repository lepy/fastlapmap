#####################################
# Fast spectral decomposition and Laplacian Eigenmaps
# Author: Davi Sidarta-Oliveira
# School of Medical Sciences,University of Campinas,Brazil
# contact: davisidarta[at]gmail.com
######################################

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse import csr_matrix
from fastlapmap.similarities import fuzzy_simplicial_set_ann, cknn_graph, diffusion_harmonics
from fastlapmap.ann import NMSlibTransformer

def LapEigenmap(data, n_eigs=10, k=10, metric='cosine', similarity='fuzzy', n_jobs=1,
                norm_laplacian=True, eigen_tol=10e-4, return_evals=False):
    """
    Performs [Laplacian Eigenmaps](https://www2.imm.dtu.dk/projects/manifold/Papers/Laplacian.pdf) on the input data.

    Parameters
    ----------
    data : numpy.ndarray, pandas.DataFrame or scipy.sparse.csr_matrix.
        Input data. If it is an array or a data frame, will use [hnswlib](https://github.com/nmslib/hnswlib) for approximate nearest-neighbors.
        If it is an sparse matrix, will use [nmslib](https://github.com/nmslib/nmslib) for approximate nearest-neighbors.
        Alternatively, users can provide an affinity matrix by stating `metric='precomputed'`.

    n_eigs : int (optional, default 10).
     Number of eigenvectors to decompose the graph Laplacian into.

    k : int (optional, default 10).
        Number of k-nearest-neighbors to use when computing affinities.

    metric : str (optional, default 'euclidean').
        which metric to use when computing neighborhood distances. Defaults to 'euclidean'.
        Accepted metrics include:
        -'sqeuclidean'
        -'euclidean'
        -'l1'
        -'lp' - requires setting the parameter `p` - equivalent to minkowski distance
        -'cosine'
        -'angular'
        -'negdotprod'
        -'levenshtein'
        -'hamming'
        -'jaccard'
        -'jansen-shan'

    similarity : str (optional, default 'diffusion').
        Which algorithm to use for similarity learning. Options are diffusion harmonics ('diffusion')
        , fuzzy simplicial sets ('fuzzy') and continuous k-nearest-neighbors ('cknn').
    n_jobs : int (optional, default 1)
        How many threads to use in approximate-nearest-neighbors computation.
    norm_laplacian : bool (optional, default True).
        Whether to renormalize the graph Laplacian.
    return_evals : bool (optional, default False).
        Whether to also return the eigenvalues in a tuple of eigenvectors, eigenvalues. Defaults to False.

    Returns
    ----------
        If return_evals is True :
            A tuple of eigenvectors and eigenvalues.
        If return_evals is False :
            An array of ranked eigenvectors.

    """
    N = np.shape(data)[0]
    if isinstance(data, np.ndarray):
        data = csr_matrix(data)
    elif isinstance(data, pd.DataFrame):
        data = data.to_numpy()
        data = csr_matrix(data)
    else:
        return print('Data should be a numpy.ndarray,pandas.DataFrame or'
                     'a scipy.sparse.csr_matrix for obtaining approximate nearest neighbors with \'nmslib\'.')

    if metric != 'precomputed':
        if similarity == 'diffusion':
            W = diffusion_harmonics(data, n_neighbors=k, metric=metric, n_jobs=n_jobs)
        elif similarity == 'fuzzy':
            fuzzy_results = fuzzy_simplicial_set_ann(data, n_neighbors=k, metric=metric, n_jobs=n_jobs)
            W = fuzzy_results[0]
        elif similarity == 'cknn':
            W = cknn_graph(data, n_neighbors=k,metric=metric, n_jobs=n_jobs, include_self=True, is_sparse=True, return_adj=False)
        # Enforce symmetry
        W = (W + W.T) / 2

    laplacian, dd = sparse.csgraph.laplacian(W, normed=norm_laplacian,
                                      return_diag=True)

    laplacian = _set_diag(laplacian, 1, norm_laplacian)

    laplacian *= -1

    n_eigs = n_eigs + 1
    evals, evecs = sparse.linalg.eigsh(laplacian, k=n_eigs, which='LM', sigma=1.0, tol=eigen_tol)
    evecs = evecs.T[n_eigs::-1]

    if norm_laplacian:
        # recover u = D^-1/2 x from the eigenvector output x
        evecs = evecs / dd
    evecs = evecs[1:n_eigs].T

    if return_evals:
        return evecs, evals
    else:
        return evecs




def _set_diag(laplacian, value, norm_laplacian):
    """Set the diagonal of the laplacian matrix and convert it to a
    sparse format well suited for eigenvalue decomposition.
    Parameters
    ----------
    laplacian : {ndarray, sparse matrix}
        The graph laplacian.
    value : float
        The value of the diagonal.
    norm_laplacian : bool
        Whether the value of the diagonal should be changed or not.
    Returns
    -------
    laplacian : {array, sparse matrix}
        An array of matrix in a form that is well suited to fast
        eigenvalue decomposition, depending on the band width of the
        matrix.
    """
    n_nodes = laplacian.shape[0]
    # We need all entries in the diagonal to values
    if not sparse.isspmatrix(laplacian):
        if norm_laplacian:
            laplacian.flat[:: n_nodes + 1] = value
    else:
        laplacian = laplacian.tocoo()
        if norm_laplacian:
            diag_idx = laplacian.row == laplacian.col
            laplacian.data[diag_idx] = value
        # If the matrix has a small number of diagonals (as in the
        # case of structured matrices coming from images), the
        # dia format might be best suited for matvec products:
        n_diags = np.unique(laplacian.row - laplacian.col).size
        if n_diags <= 7:
            # 3 or less outer diagonals on each side
            laplacian = laplacian.todia()
        else:
            # csr has the fastest matvec and is thus best suited to
            # arpack
            laplacian = laplacian.tocsr()
    return laplacian