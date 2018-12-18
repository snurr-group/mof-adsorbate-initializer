import numpy as np
import os
from ase.io import read
from mai.ads_sites import ads_pos_optimizer
from mai.tools import get_refcode
from mai.oms_handler import get_omd_data
from mai.NN_algos import get_NNs_pm
from mai.grid_handler import get_best_grid_pos
"""
This module provides classes to add adsorbates to a MOF
"""
class adsorbate_constructor():
	"""
	This class constructs an ASE atoms object with an adsorbate
	"""
	def __init__(self,ads_species,bond_dist,site_idx=None,
		d_bond=1.25,angle=None,eta=1,d_bond2=None,angle2=None,connect=1,
		r_cut=2.5,sum_tol=0.5,rmse_tol=0.25,overlap_tol=0.75):
		"""
		Initialized variables

		Args:
			ads_species (string): string of atomic element for adsorbate
			(e.g. 'O')

			bond_dist (float): distance between adsorbate and surface atom. If
			used with get_adsorbate_grid, it represents the maximum distance

			site_idx (int): ASE index for the adsorption site

			d_bond (float): X1-X2 bond length (defaults to 1.25)

			angle (float): site-X1-X2 angle (for diatomics, defaults to 180 degrees
			except for side-on in which it defaults to 90 or end-on O2 in which
			it defaults to 120; for triatomics, defaults to 180 except for H2O
			in which it defaults to 104.5)

			eta (int): denticity of end-on (1) or side-on (2) (defaults to 1)

			r_cut (float): cutoff distance for calculating nearby atoms when
			ranking adsorption sites
			
			sum_tol (float): threshold to determine planarity. when the sum
			of the Euclidean distance vectors of coordinating atoms is less
			than sum_tol, planarity is assumed
			
			rmse_tol (float): second threshold to determine planarity. when the 
			root mean square error of the best-fit plane is less than rmse_tol,
			planarity is assumed
			
			overlap_tol (float): distance below which atoms are assumed to be
			overlapping
		"""
		self.ads_species = ads_species
		self.bond_dist = bond_dist
		self.r_cut = r_cut
		self.sum_tol = sum_tol
		self.rmse_tol = rmse_tol
		self.overlap_tol = overlap_tol
		self.site_idx = site_idx

		#initialize certain variables as None
		self.d_bond = d_bond
		self.d_bond2 = d_bond2
		self.angle = angle
		self.angle2 = angle2
		self.eta = eta
		self.connect = connect

	def get_adsorbate(self,atoms_filepath,omd_path=None,NN_method='crystal',
		site_species=None,write_file=True,new_mofs_path=None,error_path=None):
		"""
		Use Pymatgen's nearest neighbors algorithms to add an adsorbate

		Args:

			atoms_filepath (string): filepath to the CIF file
			
			NN_method (string): string representing the desired Pymatgen
			nearest neighbor algorithm. options include 'crystal',vire','okeefe',
			and others. See NN_algos.py (defaults to 'crystal')

			write_file (bool): if True, the new ASE atoms object should be
			written to a CIF file (defaults to True)
			
			new_mofs_path (string): path to store the new CIF files if
			write_file is True (defaults to /new_mofs within the directory
			containing the starting CIF file)
			
			error_path (string): path to store any adsorbates flagged as
			problematic (defaults to /errors within the directory
			containing the starting CIF file)

		Returns:
			new_atoms (Atoms object): ASE Atoms object of MOF with adsorbate

			new_name (string): name of MOF with adsorbate
		"""
		#Check for file and prepare paths
		site_idx = self.site_idx
		if site_idx is not None and omd_path is not None:
			raise ValueError('Cannot provide site index and OMD results path')
		if not os.path.isfile(atoms_filepath):
			print('WARNING: No MOF found for '+atoms_filepath)
			return None, None
		if new_mofs_path is None:
			new_mofs_path = os.path.join(os.getcwd(),'new_mofs')
		if error_path is None:
			error_path = os.path.join(os.getcwd(),'errors')
		
		atoms_filename = os.path.basename(atoms_filepath)
		name = get_refcode(atoms_filename)
		atoms = read(atoms_filepath)

		#Get ASE indices of coordinating atoms and vectors from adsorption site
		if site_idx is None:
			if omd_path is None:
				omd_path = os.path.join(os.path.dirname(atoms_filepath),'oms_results')
			omsex_dict = get_omd_data(omd_path,name,atoms)
			if omsex_dict is None:
				return None, None
		else:
			NN_idx = get_NNs_pm(atoms,site_idx,NN_method)
			omsex_dict = {'cnums':[len(NN_idx)],'oms_coords':[atoms[site_idx].position],
			'oms_idx':[site_idx],'oms_sym':[atoms[site_idx].symbol],'NN_coords':[atoms[NN_idx].positions],
			'NN_idx':[NN_idx]}

		for i, oms_idx in enumerate(omsex_dict['oms_idx']):
			if omsex_dict['oms_sym'] not in site_species:
				continue
			NN_idx = omsex_dict['NN_idx'][i]
			mic_coords = np.squeeze(atoms.get_distances(oms_idx,NN_idx,
				mic=True,vector=True))

			#Get the optimal adsorption site
			ads_optimizer = ads_pos_optimizer(self,atoms_filepath,
						new_mofs_path=new_mofs_path,error_path=error_path,
						write_file=write_file)
			ads_pos = ads_optimizer.get_opt_ads_pos(mic_coords,oms_idx)
			new_atoms, new_name = ads_optimizer.get_new_atoms(ads_pos,oms_idx)
			#WRITE THESE OUT TO A LIST

		return new_atoms, new_name

	def get_adsorbate_grid(self,atoms_filepath,grid_path=None,
		grid_format='ASCII',write_file=True,new_mofs_path=None,error_path=None):
		"""
		This function adds a molecular adsorbate based on an ASCII-formatted
		energy grid (such as via RASPA)

		Args:
			atoms_filepath (string): filepath to the CIF file
			
			grid_path (string): path to the directory containing the PEG
			(defaults to /energy_grids within the directory containing
			the starting CIF file)

			grid_format (string): accepts either 'ASCII' or 'cube' and
			is the file format for the PEG (defaults to ASCII)

			write_file (bool): if True, the new ASE atoms object should be
			written to a CIF file (defaults to True)
			
			new_mofs_path (string): path to store the new CIF files if
			write_file is True (defaults to /new_mofs within the directory
			containing the starting CIF file)
			
			error_path (string): path to store any adsorbates flagged as
			problematic (defaults to /errors within the directory
			containing the starting CIF file)

		Returns:
			new_atoms (Atoms object): ASE Atoms object of MOF with adsorbate
			
			new_name (string): name of MOF with adsorbate
		"""
		#Check for file and prepare paths
		
		self.ads_species += '_grid'
		if not os.path.isfile(atoms_filepath):
			print('WARNING: No MOF found for '+atoms_filepath)
			return None, None

		grid_format = grid_format.lower()
		if grid_format == 'ascii':
			grid_ext = '.grid'
		elif grid_format == 'cube':
			grid_ext = '.cube'
		else:
			raise ValueError('Unsupported grid_format '+grid_format)

		if self.site_idx is None:
			raise ValueError('site_idx must be specified')

		if grid_path is None:
			grid_path = os.path.join(os.path.dirname(atoms_filepath),'energy_grids')
		if new_mofs_path is None:
			new_mofs_path = os.path.join(os.getcwd(),'new_mofs')
		if error_path is None:
			error_path = os.path.join(os.getcwd(),'errors')

		max_dist = self.bond_dist
		site_idx = self.site_idx

		atoms_filename = os.path.basename(atoms_filepath)
		name = get_refcode(atoms_filename)
		atoms = read(atoms_filepath)
		grid_filepath = os.path.join(grid_path,name+grid_ext)
		
		site_pos = atoms[site_idx].position
		ads_pos = get_best_grid_pos(atoms,max_dist,site_idx,grid_filepath)
		if ads_pos is 'nogrid':
			print('WARNING: no grid for '+name)
			return None, None
		elif ads_pos is 'invalid':
			print('WARNING: all NaNs within cutoff for '+name)
			return None, None
		ads_optimizer = ads_pos_optimizer(self,atoms_filepath,
					new_mofs_path=new_mofs_path,error_path=error_path,
					write_file=write_file)
		new_atoms, new_name = ads_optimizer.get_new_atoms_grid(site_pos,ads_pos)

		return new_atoms, new_name