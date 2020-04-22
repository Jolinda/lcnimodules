# only works if dicom files are sorted into subdirectories by series!
# You must define the bids_dict & bids_dir for your study
# Assumes 1 session per subject


# valid entity information Does not include most non-mri file types
filetypes = ['anat', 'func', 'dwi', 'fmap']

# not validating against these yet, information only
formats = dict()
formats['anat'] = ['T1w', 'T2w', 'FLAIR', 'T1rho', 'T1map', 'T2map', 'T2star',
					'FLASH', 'PD', 'PDmap', 'PDT2', 'inplaneT1', 'inplaneT2', 
					'angio, defacemask']
formats['fmap'] = ['phasediff', 'phase1', 'phase2', 'magnitude1', 'magnitude2',
					 'magnitude', 'fieldmap', 'epi']
formats['dwi'] = ['dwi', 'bvec', 'bval']
formats['func'] = ['bold', 'cbv', 'phase', 'sbref', 'events', 'physio', 'stim']

import re
dicom_pattern = re.compile('(.*)_([0-9]{8})(.*)')    
series_pattern = re.compile('.*Series_([0-9]*)_(.*)')

import os

def GetSeriesNames(directory):
	return set([re.match(series_pattern, x[0]).group(2) for x in os.walk(directory) if 'Series' in x[0]])
#	return set([x[0] for x in os.walk(directory) if 'Series' in x])

class entity:
	def __init__(self, filetype, session = None, task = None, acq = None, form = None,
		phase_encoding = None):
		if filetype not in filetypes:
			raise ValueError('Unknown filetype'.format(filetype))
		# we could do more validating, add later
		self.filetype = filetype
		self.session = session
		self.task = task
		self.acq = acq
		self.form = form
		self.phase_encoding = phase_encoding

	def __str__(self):
		return_string = self.filetype + ': sub-x'
		if self.session:
			return_string += '_ses-{}'.format(self.session)
		if self.task:
			return_string += '_task-{}'.format(self.task)
		if self.acq:
			return_string += '_acq-{}'.format(self.acq)
		if self.phase_encoding:
			return_string += '_dir-{}'.format(self.phase_encoding)
		return_string += '_run-n'
		if self.form:
			return_string += '_{}'.format(self.form)
		return return_string

	def __repr__(self):
		return_string = 'filetype: {}, session: {}, task: {}, acq: {}, phase_encoding: {}, form: {}'.format(
				self.filetype, self.session, self.task, self.acq, self.phase_encoding, self.form)
		return return_string



# explains how to map from series names to bids entries
class bids_dict:
	def __init__(self):
		self.dictionary = dict()

	def add(self, series_descripton, filetype, session = None, task = None,
		acq = None, form = None, phase_encoding = None):

		self.dictionary[series_descripton] = entity(filetype = filetype, session = session,
			task = task, acq = acq, form = form, phase_encoding = phase_encoding)
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


def convert(subjectdir, bidsdir, bids_dict, submit = True):
	
	if not os.path.exists(bidsdir) and submit:
		os.makedirs(bidsdir)

	import json
	projectname = os.path.basename(os.path.dirname(subjectdir))
	description_file = os.path.join(bidsdir, 'dataset_description.json')
	j = {'Name':projectname, 'BIDSVersion':'1.3.0'}
	if not submit:
		print(j)
	if not os.path.exists(description_file) and submit:		
		with open(description_file, 'w') as f:
			json.dump(j, f)
	
	#for task in [entity['task'] for entity in bids_dict.dictionary if entity['task']]:
	#	print(task)

	name = re.search(dicom_pattern, os.path.basename(subjectdir)).group(1)

	command = 'module load dcm2niix\n'
	command += 'module load jq\n'

	subj_dir = os.path.join(bidsdir, 'sub-{}'.format(name))
	series_dirs = os.listdir(subjectdir)
	for series in series_dirs:
		run, series_name = re.match(series_pattern, series).groups()
		output_dir = None
		if series_name in bids_dict.dictionary:
			entity = bids_dict.dictionary[series_name]
			output_dir = os.path.join(subj_dir, entity.filetype)
			format_string =  'sub-%n'
			if entity.session:
				format_string += '_ses-{}'.format(entity.session)
			if entity.task:
				format_string += '_task-{}'.format(entity.task)
			if entity.acq:
				format_string += '_acq-{}'.format(entity.acq)
			if entity.phase_encoding:
				format_string += '_dir-{}'.format(entity.phase_encoding)

			format_string += '_run-{}'.format(run)

			if entity.form:
				format_string += '_{}'.format(entity.form)

			if not os.path.exists(output_dir):
				os.makedirs(output_dir)

			command += 'dcm2niix -ba n -o {} -f {} {}\n'.format(output_dir,
						format_string, os.path.join(subjectdir, series))

			#if entity.task:
			#	task_json = '{}*_task-{}*_run-{}_*.json'.format(output_dir, entity.task, run)
			#	command += 'jq \'.TaskName="{0}"\' {1} > {1}\n'.format(entity.task, task_json)
			
	if submit:
		import slurmpy
		job = slurmpy.slurmjob(jobname = 'convert', command = command, srun_directory = '/tmp')
		job.WriteSlurmFile(printfile = False)
		job.SubmitSlurmFile()
	else :
		print(command)

	return command