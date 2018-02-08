"""Particle fingerprint functions."""
from __future__ import absolute_import
from __future__ import division

import numpy as np
from itertools import product

from ase.ga.utilities import (get_atoms_distribution,
                              get_neighborlist, get_atoms_connections, get_rdf)

from .base import BaseGenerator

no_asap = False
try:
    from asap3.analysis.rdf import RadialDistributionFunction
except ImportError:
    no_asap = True


class ParticleFingerprintGenerator(BaseGenerator):
    """Function to build a fingerprint vector based on an atoms object."""

    def __init__(self, **kwargs):
        """Particle fingerprint generator setup.

        Parameters
        ----------
        atom_types : list
            List of unique atomic numbers.
        max_bonds : int
            Count up to the specified number of bonds. Default is 0 to 12.
        get_nl : boolean
            Specify whether to recalculate the neighborlist. Default is False.
        dx : float
            Cutoff added to the covalent radii to calculate the neighborlist.
        cell_size : float
            Set unit cell size, default is 50.0 angstroms.
        nbin : int
            The number of bins supplied to the get_atoms_distribution function.
        """
        if not hasattr(self, 'atom_types'):
            self.atom_types = kwargs.get('atom_types')

        self.max_bonds = kwargs.get('max_bonds', 13)
        self.get_nl = kwargs.get('get_nl', False)
        self.dx = kwargs.get('dx', 0.2)
        self.cell_size = kwargs.get('cell_size', 50.)
        self.nbin = kwargs.get('nbin', 4)
        self.nbins = kwargs.get('nbins', 5)
        self.rmax = kwargs.get('rmax', 8.)

        super(ParticleFingerprintGenerator, self).__init__(**kwargs)

    def nearestneighbour_vec(self, data):
        """Nearest neighbour average, Topics in Catalysis, 2014, 57, 33.

        This is a slightly modified version of the code found in the `ase.ga`
        module.

        Parameters
        ----------
        data : object
            Data object with atomic numbers available.
        """
        elements = sorted(set(self.get_atomic_numbers(data)))
        nnmat = np.zeros((len(elements), len(elements)))
        dm = self.get_all_distances(data)
        rdf, dists = get_rdf(data, 10., 200, dm)
        nndist = dists[np.argmax(rdf)] + 0.2

        for i in range(len(data)):
            row = [j for j in range(len(elements))
                   if data[i].number == elements[j]][0]
            neighbors = [j for j in range(len(dm[i])) if dm[i][j] < nndist]
            for n in neighbors:
                column = [j for j in range(len(elements))
                          if data[n].number == elements[j]][0]
                nnmat[row][column] += 1

        for i, el in enumerate(elements):
            nnmat[i] /= len([j for j in range(len(data))
                             if data[int(j)].number == el])

        nnlist = np.reshape(nnmat, (len(nnmat)**2))

        return nnlist

    def bond_count_vec(self, data):
        """Bond counting with a distribution measure for coordination."""
        elements = sorted(set(self.get_atomic_numbers(data)))

        # Get coordination number counting.
        dm = self.get_all_distances(data)
        rdf, dists = get_rdf(data, 10., 200, dm)
        nndist = dists[np.argmax(rdf)] + 0.2
        track_nnmat = np.zeros((self.max_bonds, len(elements), len(elements)))
        for j in range(len(data)):
            row = elements.index(data[j].number)
            neighbors = [k for k in range(len(dm[j]))
                         if 0.1 < dm[j][k] < nndist]
            ln = len(neighbors)
            if ln > 12:
                continue
            for l in neighbors:
                column = elements.index(data[l].number)
                track_nnmat[ln][row][column] += 1

        return track_nnmat.ravel()

    def distribution_vec(self, atoms):
        """Return atomic distribution measure."""
        # Center the atoms, works better for some utility functions.
        atoms.set_cell([self.cell_size, self.cell_size, self.cell_size])
        atoms.center()

        if self.get_nl:
            # Define the neighborlist.
            atoms.info['data']['neighborlist'] = get_neighborlist(atoms,
                                                                  dx=self.dx)

        # If unique atomic numbers not supplied. Generate it now.
        if self.atom_types is None:
            self.atom_types = frozenset(atoms.get_atomic_numbers())
        # Get the atomic distribution of each atom type.
        dist = []
        for i in self.atom_types:
            dist += get_atoms_distribution(atoms, number_of_bins=self.nbin,
                                           no_count_types=[i])
        return dist

    def connections_vec(self, atoms):
        """Sum atoms with a certain number of connections."""
        if self.get_nl:
            # Define the neighborlist.
            atoms.info['data']['neighborlist'] = get_neighborlist(atoms,
                                                                  dx=self.dx)

        fp = []
        if self.atom_types is None:
            # Get unique atom types.
            self.atom_types = frozenset(atoms.get_atomic_numbers())
        for an in self.atom_types:
            conn = get_atoms_connections(atoms, max_conn=self.max_bonds,
                                         no_count_types=[an])
            for i in conn:
                fp.append(i)

        return fp

    def rdf_vec(self, atoms):
        """Return list of partial rdfs for use as fingerprint vector."""
        if not no_asap:
            rf = RadialDistributionFunction(atoms,
                                            rMax=self.rmax,
                                            nBins=self.nbins).get_rdf
            kwargs = {}
        else:
            rf = get_rdf
            dm = atoms.get_all_distances()
            kwargs = {'atoms': atoms, 'rmax': self.rmax,
                      'nbins': self.nbins, 'no_dists': True,
                      'distance_matrix': dm}

        fp = []
        for c in product(set(atoms.numbers), repeat=2):
            fp.extend(rf(elements=c, **kwargs))

        return fp
