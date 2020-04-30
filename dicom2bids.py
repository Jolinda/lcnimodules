# only works if dicom files are sorted into subdirectories by series!
# You must define the bids_dict & bids_dir for your study
# Assumes 1 session per subject


# valid entity information Does not include most non-mri file types
filetypes = ['anat', 'func', 'dwi', 'fmap']

# not validating against these yet, information only
formats = dict()
formats['anat'] = ['T1w', 'T2w', 'FLAIR', 'T1rho', 'T1map', 'T2map', 'T2star',
					'FLASH', 'PD', 'PDmap', 'PDT2', 'inplaneT1', 'inplaneT2', 
					'angio', 'defacemask']
formats['fmap'] = ['phasediff', 'phase1', 'phase2', 'magnitude1', 'magnitude2',
					 'magnitude', 'fieldmap', 'epi']
formats['dwi'] = ['dwi', 'bvec', 'bval']
formats['func'] = ['bold', 'cbv', 'phase', 'sbref', 'events', 'physio', 'stim']

import re
dicom_pattern = re.compile('(.*)_([0-9]{8})(.*)')    
series_pattern = re.compile('.*Series_([0-9]*)_(.*)')

import os, json

def GetSeriesNames(directory):
	return set([re.match(series_pattern, x[0]).group(2) for x in os.walk(directory) if 'Series' in x[0]])
#	return set([x[0] for x in os.walk(directory) if 'Series' in x])

class entity:
	def __init__(self, filetype, form, session = None, task = None, acq = None, phase_encoding = None,
		ce = None, rec = None):
		if filetype not in filetypes:
			raise ValueError('Unknown filetype'.format(filetype))
		# we could do more validating, add later
		self.filetype = filetype
		self.session = session
		self.task = task
		self.acq = acq
		self.form = form
		self.phase_encoding = phase_encoding
		self.ce = ce
		self.rec = rec



	def __repr__(self):
		return_string = 'filetype: {}, session: {}, task: {}, acq: {}, phase_encoding: {},'.format(
				self.filetype, self.session, self.task, self.acq, self.phase_encoding)
		return_string += 'ce: {}, rec: {}, form: {}'.format(self.ce, self.rec, self.form)
		return return_string


	def GetFormatString(self):
		format_string =  'sub-{}'
		if self.session:
			format_string += '_ses-{}'.format(self.session)
		if self.task:
			format_string += '_task-{}'.format(self.task)
		if self.acq:
			format_string += '_acq-{}'.format(self.acq)
		if self.phase_encoding:
			format_string += '_dir-{}'.format(self.phase_encoding)
		if self.ce:
			format_string += '_dir-{}'.format(self.ce)
		if self.rec:
			format_string += '_dir-{}'.format(self.rec)

		format_string += '_run-{}'

		if self.form:
			format_string += '_{}'.format(self.form)

		return format_string

	def __str__(self):
		return self.GetFormatString()



# explains how to map from series names to bids entries
class bids_dict:
	def __init__(self):
		self.dictionary = dict()

	def add(self, series_descripton, filetype, form, session = None, task = None,
		acq = None, phase_encoding = None, ce = None, rec = None):

		self.dictionary[series_descripton] = entity(filetype = filetype, session = session,
			task = task, acq = acq, form = form, phase_encoding = phase_encoding, ce = ce, rec = rec)
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
		j['Acknowledgements'] = 'BIDS conversion was performed using dcm2niix. Thanks to Jolinda Smith at LCNI at the University of Oregon for additional scripting of BIDS conversion.'
		j['ReferencesAndLinks'] = ['Li X, Morgan PS, Ashburner J, Smith J, Rorden C (2016) The first step for neuroimaging data analysis: DICOM to NIfTI conversion. J Neurosci Methods. 264:47-56. doi: 10.1016/j.jneumeth.2016.03.001.']
		with open(description_file, 'w') as f:
			json.dump(j, f)

def AppendParticipant(subjectdir, bidsdir):
	if not os.path.exists(bidsdir):
		os.makedirs(bidsdir)

	name = re.search(dicom_pattern, os.path.basename(subjectdir.strip('/'))).group(1)
	# check for name in .tsv first
	part_file = os.path.join(bidsdir, 'participants.tsv')
	import csv

	if os.path.exists(part_file):
		with open(part_file) as tsvfile:
			reader = csv.DictReader(tsvfile, dialect='excel-tab')
			fieldnames = reader.fieldnames
			subjects = [row['participant_id'] for row in reader]

		# return if this subject is already there
		if 'sub-{}'.format(name) in subjects:
			return
	else:
		fieldnames = ['participant_id', 'age', 'sex']
		with open(part_file, 'w') as tsvfile:
			writer = csv.DictWriter(tsvfile, fieldnames, dialect='excel-tab', 
				extrasaction = 'ignore')
			writer.writeheader()


	# get any dicom file
	import glob
	dcmfile = next(x for x in glob.glob(os.path.join(subjectdir,
		'Series*', '*.dcm')))
	import pydicom
	ds = pydicom.dcmread(dcmfile)

	with open(part_file, 'a') as tsvfile:
		writer = csv.DictWriter(tsvfile, fieldnames, dialect='excel-tab', 
			extrasaction = 'ignore')
		writer.writerow({'participant_id': 'sub-{}'.format(name), 
			'sex':ds.PatientSex, 'age':ds.PatientAge[:-1]})
	return



def convert(subjectdir, bidsdir, bids_dict, submit = True, participant_file = True, 
	json_mod = None, dcm2niix_flags = ''):
	
	if not os.path.exists(bidsdir) and submit:
		os.makedirs(bidsdir)

	if submit:
		WriteDescription(subjectdir, bidsdir)

	if participant_file and submit:
		AppendParticipant(subjectdir, bidsdir)

	name = re.search(dicom_pattern, os.path.basename(subjectdir.strip('/'))).group(1)

	command = 'module load dcm2niix\n'
	command += 'module load jq\n'

	subj_dir = os.path.join(bidsdir, 'sub-{}'.format(name))
	series_dirs = os.listdir(subjectdir)

	for series in series_dirs:
		run, series_name = re.match(series_pattern, series).groups()
		output_dir = None
		if series_name in bids_dict.dictionary:
			entity = bids_dict.dictionary[series_name]

			if entity.session:
				output_dir = os.path.join(subj_dir, 'ses-{}'.format(entity.session),
				entity.filetype)
			else:
				output_dir = os.path.join(subj_dir, entity.filetype)

			format_string = entity.GetFormatString().format(name, run)

			if not os.path.exists(output_dir):
				os.makedirs(output_dir)

			command += 'dcm2niix -ba n -l o -o {} -f {} {} {}\n'.format(output_dir,
						format_string, dcm2niix_flags, os.path.join(subjectdir, series))

			json_file = os.path.join(output_dir, format_string + '.json')
			if entity.task:
				#command += 'jq \'.TaskName="{0}"\' {1} > {1}\n'.format(entity.task, task_json)
				command += FixJson(json_file, 'TaskName', entity.task)

			if json_mod:
				for key in json_mod:
					command += FixJson(json_file, key, json_mod[key])

	if submit:
		import slurmpy
		job = slurmpy.slurmjob(jobname = 'convert', command = command)
		job.WriteSlurmFile(filename = '/tmp/convert.srun')
		job.SubmitSlurmFile()

	return command


# Given a path into the talapas dcm repo, generate a list of authors
def GetAuthors(dicompath):
	authorlist = set() # no duplicates
	
	# first add current user
	import getpass
	user = getpass.getuser()
	import pwd
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
	command =  'jq \'.{1}="{2}"\' {0} > \\tmp\{3}\n'.format(filename, key, value, os.path.basename(filename))
	command += 'mv \\tmp\{} {}\n'.format(os.path.basename(filename), filename)
	return(command)

# usual things wrong in lcni dicoms pre 4/30/2020
lcni_corrections = {'InstitutionName':'University of Oregon', 'InstitutionalDepartmentName':'LCNI', 'InstitutionAddress':'Franklin_Blvd_1440_Eugene_Oregon_US_97403'}
