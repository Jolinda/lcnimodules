import tempfile
import re
import json
import subprocess
import os
import glob
import shutil
import pwd
import getpass
import csv

import pydicom

## todo: pathlib

# valid datatype information
datatypes = ['anat', 'func', 'dwi', 'fmap', 'meg', 'eeg', 'ieeg', 'beh']

entities = ['ses', 'task', 'acq', 'ce', 'rec', 'dir', 'run', 'mod', 'echo', 'recording', 'proc', 'space']

# valid suffixes for datatypes
suffixes = dict()
suffixes['anat'] = ['T1w', 'T2w', 'FLAIR', 'T1rho', 'T1map', 'T2map', 'T2star',
					'FLASH', 'PD', 'PDmap', 'PDT2', 'inplaneT1', 'inplaneT2', 
					'angio', 'defacemask']
suffixes['fmap'] = ['phasediff', 'phase1', 'phase2', 'magnitude1', 'magnitude2',
					 'magnitude', 'fieldmap', 'epi']
suffixes['dwi'] = ['dwi', 'bvec', 'bval']
suffixes['func'] = ['bold', 'cbv', 'phase', 'sbref', 'events', 'physio', 'stim']

subject_pattern = re.compile('(.*)_([0-9]{8})(.*)')    
series_pattern = re.compile('.*Series_([0-9]*)_(.*)')


def GetSeriesNames(directory):
	return set([re.match(series_pattern, x[0]).group(2) for x in os.walk(directory) if 'Series' in x[0]])

def GetSubjectName(directory):
	name = re.search(subject_pattern, os.path.basename(directory.strip('/'))).group(1)
	return re.sub('[^0-9a-zA-Z]+', '', name)

class entity_chain:
	def __init__(self, datatype, suffix, nonstandard = False, **kwargs):
		
		if not nonstandard:
			if datatype not in datatypes:
				raise ValueError('Unknown data type {}'.format(datatype))

			if suffix not in suffixes[datatype]:
				error_string = 'Unknown suffix {} for data type {}\n'.format(suffix, datatype)
				error_string += 'Allowed suffixes are {}'.format(suffixes[datatype])
				raise ValueError(error_string)
		
		self.datatype = datatype
		self.suffix = suffix

		## lets folks explicitly write entities = {'arg':'value'}
		## and/or arg = 'value', usual **kwargs way
		self.chain = kwargs
		if 'entities' in kwargs:
			del(self.chain['entities'])
			self.chain.update(kwargs['entities'])
		

		if not self.chain:
			self.chain = dict()

		self.chain['run'] = '{}'




	def __repr__(self):
		return_string = 'datatype: {}, suffix: {}, entities: {}'.format(self.datatype, self.suffix, self.chain)
		return return_string


	def GetFormatString(self):
		format_string =  'sub-{}_'
		if self.chain:
			for key, value in [(k, self.chain[k]) for k in entities if k in self.chain]:
				format_string += '{}-{}_'.format(key, value)

		format_string += '{}'.format(self.suffix)

		return format_string

	def __str__(self):
		return self.GetFormatString()



# explains how to map from series names to bids entries
class bids_dict:
	def __init__(self):
		self.dictionary = dict()

	def add(self, series_descripton, datatype, suffix, nonstandard = False, **kwargs):

		# seems awkward
		chain = dict(kwargs)
		if 'entities' in kwargs:
			del(chain['entities'])
			chain.update(kwargs['entities'])

		self.dictionary[series_descripton] = entity_chain(datatype = datatype, suffix = suffix, 
			nonstandard = nonstandard, **chain)
		
	def __str__(self):
		return_string = str()
		for series in self.dictionary:
			return_string += '{}: {}\n'.format(series, self.dictionary[series])
		return return_string

	def __repr__(self):
		return_string = str()
		for series in self.dictionary:
			return_string += '{}: {}\n'.format(series, self.dictionary[series].__repr__())
		return return_string

def WriteDescription(subjectdir, bidsdir):
	projectname = os.path.basename(os.path.dirname(subjectdir))
	description_file = os.path.join(bidsdir, 'dataset_description.json')

	if not os.path.exists(description_file):		
		projectname = os.path.basename(os.path.dirname(subjectdir))
		j = {'Name':projectname, 'BIDSVersion':'1.3.0'}
		j['Authors'] =  GetAuthors(subjectdir)
		j['Acknowledgements'] = 'BIDS conversion was performed using dcm2niix and py2bids.'
		j['ReferencesAndLinks'] = ['Li X, Morgan PS, Ashburner J, Smith J, Rorden C (2016) The first step for neuroimaging data analysis: DICOM to NIfTI conversion. J Neurosci Methods. 264:47-56. doi: 10.1016/j.jneumeth.2016.03.001.']
		with open(description_file, 'w') as f:
			json.dump(j, f)

def AppendParticipant(subjectdir, bidsdir):
	if not os.path.exists(bidsdir):
		os.makedirs(bidsdir)

	name = GetSubjectName(subjectdir)
	# check for name in .tsv first
	part_file = os.path.join(bidsdir, 'participants.tsv')

	if os.path.exists(part_file):
		with open(part_file) as tsvfile:
			reader = csv.DictReader(tsvfile, dialect='excel-tab')
			
			# get the field name
			fieldnames = reader.fieldnames
			
			subjects = [row['participant_id'] for row in reader]
		# return if this subject is already there
		if 'sub-{}'.format(name) in subjects:
			return
		
	else: # create new tsv/json files
		fieldnames = ['participant_id', 'age', 'sex']
		with open(part_file, 'w') as tsvfile:
			writer = csv.DictWriter(tsvfile, fieldnames, dialect='excel-tab', 
				extrasaction = 'ignore')
			writer.writeheader()
		json_file = os.path.join(bidsdir, 'participants.json')
		j = {'age': {'Description': 'age of participant', 'Units': 'years'}, 
		'sex': {'Description': 'sex of participant', 'Levels': {'M': 'male', 'F': 'female', 'O': 'other'}}}
		with open(json_file, 'w') as f:
			json.dump(j, f)


	# get any dicom file
	dcmfile = next(x for x in glob.glob(os.path.join(subjectdir,
		'Series*', '*.dcm')))
	ds = pydicom.dcmread(dcmfile)

	with open(part_file, 'a') as tsvfile:
		writer = csv.DictWriter(tsvfile, fieldnames, dialect='excel-tab', 
			extrasaction = 'ignore')
		writer.writerow({'participant_id': 'sub-{}'.format(name), 
			'sex':ds.PatientSex, 'age':int(ds.PatientAge[:-1])})
	return

def Convert(dicomdir, bidsdir, bids_dict, slurm = False, participant_file = True, description_file = True,
	json_mod = None, dcm2niix_flags = '', throttle = False, account = None, 
	lmod = ['dcm2niix', 'jq']):

	subjectdirs = [x[0] for x in os.walk(dicomdir) if subject_pattern.match(os.path.basename(x[0].strip('/')))]
	
	if not subjectdirs:
		raise ValueError('Unable to find subject level directories. Are dicoms in lcni standard directory structure? You may need to run dicom2bids.SortDicoms({}) first.'.format(dicomdir))

	if not os.path.exists(bidsdir):
		os.makedirs(bidsdir)

	if description_file:
		WriteDescription(subjectdirs[0], bidsdir)

	command_base = ''
	for mod in lmod:
		command_base += 'module load {}\n'.format(mod)

	for subjectdir in sorted(subjectdirs):

		if participant_file:
			AppendParticipant(subjectdir, bidsdir)

		command = command_base + GenerateCSCommand(subjectdir = subjectdir, bidsdir = bidsdir, bids_dict = bids_dict,
			json_mod = json_mod, dcm2niix_flags = dcm2niix_flags)

		if slurm:
			import slurmpy
			job = slurmpy.SlurmJob(jobname = 'convert', command = command, account = account)
			filename = tempfile.NamedTemporaryFile().name
			job.WriteSlurmFile(filename = filename)
			job.SubmitSlurmFile()
			if throttle:
				slurmpy.SlurmThrottle() # Mike's helper script, helps with large # of submissions

		else:
			#print(command)
			process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, shell = True)






def GenerateCSCommand(subjectdir, bidsdir, bids_dict, json_mod = None, dcm2niix_flags = ''):

	name = GetSubjectName(subjectdir)

	command = ''

	subj_dir = os.path.join(bidsdir, 'sub-{}'.format(name))
	series_dirs = os.listdir(subjectdir)

	for series in series_dirs:
		run, series_name = re.match(series_pattern, series).groups()
		output_dir = None
		if series_name in bids_dict.dictionary:
			echain = bids_dict.dictionary[series_name]

			if 'ses' in echain.chain:
				output_dir = os.path.join(subj_dir, 'ses-{}'.format(echain.chain['ses']),
					echain.datatype)
			else:
				output_dir = os.path.join(subj_dir, echain.datatype)

			echain.chain['run'] = '{:02d}'.format(int(run))
			format_string = echain.GetFormatString().format(name)

			if not os.path.exists(output_dir):
				os.makedirs(output_dir)

			command += 'dcm2niix -ba n -l o -o "{}" -f {} {} "{}"\n'.format(output_dir,
						format_string, dcm2niix_flags, os.path.join(subjectdir, series))

			json_file = os.path.join(output_dir, format_string + '.json')
			if 'task' in echain.chain:
				command += FixJson(json_file, 'TaskName', echain.chain['task'])

			if json_mod:
				for key in json_mod:
					command += FixJson(json_file, key, json_mod[key])

			if echain.datatype == 'dwi':
				command += FixDwiFiles(output_dir)



	return command


# Given a path into the talapas dcm repo, generate a list of authors
def GetAuthors(dicompath):
	authorlist = set() # no duplicates
	
	# first add current user
	user = getpass.getuser()
	authorlist.add(pwd.getpwnam(user).pw_gecos)

	# add pi from pirg if possible
	if dicompath.startswith('/projects/lcni/dcm/'):
		pirg = dicompath.split('/')[4]
		if os.path.exists(os.path.join('/projects', pirg)):
			pi_uid = os.stat(os.path.join('/projects', pirg)).st_uid
			pi_name = pwd.getpwuid(pi_uid).pw_gecos
			authorlist.add(pi_name)

	return list(authorlist)

# returns the jq command string to add or modify a json file 
def FixJson(filename, key, value):
	command =  'jq \'.{1}="{2}"\' {0} > /tmp/{3}\n'.format(filename, key, value, os.path.basename(filename))
	command += 'mv /tmp/{} {}\n'.format(os.path.basename(filename), filename)
	return(command)

# returns the command string to rename bval and bvecs files
def FixDwiFiles(dirname):
	command = 'for x in {}/*dwi.bv*\n'.format(dirname)
	command += 'do mv $x ${x//dwi.}\n'
	command += 'done\n'
	return(command)

# usual things wrong in lcni dicoms pre 4/30/2020
lcni_corrections = {'InstitutionName':'University of Oregon', 'InstitutionalDepartmentName':'LCNI', 'InstitutionAddress':'Franklin_Blvd_1440_Eugene_Oregon_US_97403'}


def SortDicoms(input_dir, output_dir, overwrite = False, preview = False, slurm = False, account = None):

	if slurm:
		command = 'import dicom2bids\n'
		command += 'dicom2bids.SortDicoms("{}","{}", overwrite = {}, preview = {}, slurm = False)'.format(input_dir, output_dir, overwrite, preview)

		import slurmpy
		filename = tempfile.NamedTemporaryFile().name
		job = slurmpy.SlurmJob(jobname = 'sort', command = command, account = account)
		job.WriteSlurmFile(filename = filename, interpreter = 'python')
		return job.SubmitSlurmFile()

	# Get the list of all files in directory tree at given path
	listOfFiles = list()
	for (dirpath, dirnames, filenames) in os.walk(input_dir):
		listOfFiles += [os.path.join(dirpath, file) for file in filenames]

	duplicates = False

	for file in listOfFiles:
		try:
			ds = pydicom.dcmread(file)
		except:
			print('Unable to read as dicom: ', file)
			continue

		subject = ds.PatientName
		date = ds.StudyDate
		time = ds.StudyTime.split('.')[0]
		series_no = ds.SeriesNumber
		series_desc = ds.SeriesDescription
		  
		  
		newname = os.path.join(output_dir, '{}_{}_{}'.format(subject, date, time), 
			'Series_{}_{}'.format(series_no, series_desc), os.path.basename(file))

		if preview:
			print(file, '-->', newname)

		elif not overwrite and os.path.exists(newname):
			duplicates = True
		else:
			os.makedirs(os.path.dirname(newname), exist_ok = True)
			shutil.copyfile(file, newname)


	if duplicates:
		print('One or more files already existing and not moved')


