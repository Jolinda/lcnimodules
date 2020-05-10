import subprocess
import os
import glob

def OnTalapas():
	groups = subprocess.run(['groups'], stdout = subprocess.PIPE, universal_newlines = True).stdout.strip().split()
	return 'talapas' in groups


# talapas only script from Mike Coleman
# /packages/racs/bin/slurm-throttle
def SlurmThrottle():
	subprocess.run(['/packages/racs/bin/slurm-throttle'])

def SubmitSlurmFile(filename):
	if not os.path.exists(filename):
		print('{} not found'.format(filename))
		return None
	process = subprocess.run(['sbatch', filename], stdout=subprocess.PIPE, 
							 stderr=subprocess.STDOUT, universal_newlines=True)

	print(process.stdout)

	if process.stdout.split()[0] == 'Submitted':
		jobnumber = process.stdout.split()[-1]
	else :
		jobnumber = None
			
	return jobnumber

import time
def WaitUntilComplete(jobnumber):
	time.sleep(10)
	while True:
		if not AnyJobs(jobnumber, 'PENDING') and not AnyJobs(jobnumber, 'RUNNING'):
			if AllJobs(jobnumber,'COMPLETED'):
				print('Job complete')
				return
			else:
				print(JobStatus(jobnumber))
				assert False

		if AnyJobs(jobnumber, 'PENDING'):
			queue = subprocess.run('squeue', stdout=subprocess.PIPE, 
							 stderr=subprocess.STDOUT, universal_newlines=True).stdout
			for line in queue.split('\n'):
				if jobnumber in line and 'ReqNodeNotAvail' in line:
					print(line)
					assert False

		time.sleep(10)

## submit command to slurm using "wrap"
## moving some arguments to slurm_params
def WrapSlurmCommand(command, jobname =None, index = None, 
					 output_directory = None, dependency = None, email = None, 
					 threads = None, deptype = 'ok', **slurm_params):


	slurm = 'sbatch '

	if jobname:
		slurm += '--job-name={} '.format(jobname)
	
	if index:
		slurm += '--comment=idx:{} '.format(index)
	
	if email:
		slurm += '--mail-user={} --mail-type=END '.format(email)
		
	if dependency:
		slurm += '--dependency=after{}:{} '.format(deptype, dependency)
		
	if threads:
		slurm += '--cpus-per-task={} '.format(threads)

	for arg in slurm_params:
		slurm += '--{}={} '.format(arg, slurm_params[arg])
		
	if output_directory:
			if not os.path.exists(output_directory):
				os.mkdir(output_directory)
			slurm += '--output={}/%x-%j.out '.format(output_directory)
			slurm += '--error={}/%x-%j.err '.format(output_directory)

	if type(command) is str:
		command = [command]
		
	slurm += '--wrap \"' + '\n'.join(command) + '"'
	
	print(slurm)
	process = subprocess.run(slurm, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
								 universal_newlines=True, shell=True)

	print(process.stdout)

	if process.stdout.split()[0] == 'Submitted':
		return process.stdout.split()[-1]
	else :
		return None


def WriteSlurmFile(jobname, command, filename = None, interpreter = 'bash', index = None,  
				   data_list = None, variable = 'x', output_directory = None, dependency = None,
				   threads = None, array_limit = None, deptype = 'ok', email = None, **slurm_params):
	
	if not filename:
		filename = jobname + '.srun'

	with open (filename, 'w') as f:
		if interpreter == 'python':
			import sys
			f.write('#!{}\n'.format(sys.executable))

		elif interpreter == 'bash':
			f.write('#!/bin/bash\n')
			
		else : # caller sent full path to interpreter
			f.write('#!{}\n'.format(interpreter))

		f.write('#SBATCH --job-name={}\n'.format(jobname))

		if email:
			f.write('#SBATCH --mail-user={}\n'.format(email))
			f.write('#SBATCH --mail-type=END\n')

		if dependency:
			 f.write('#SBATCH --dependency=after{}:{}\n'.format(deptype, dependency))

		if threads:
			f.write('#SBATCH --cpus-per-task={}\n'.format(threads))

		if index:
			f.write('#SBATCH --comment=idx:{}\n'.format(index))

		for arg in slurm_params:
			f.write('#SBATCH --{}={}\n'.format(arg, slurm_params[arg]))

		if output_directory:
			if not os.path.exists(output_directory):
				os.mkdir(output_directory)
			if data_list:
				f.write('#SBATCH --output={}/%x-%A_%a.out\n'.format(output_directory))
				f.write('#SBATCH --error={}/%x-%A_%a.err\n\n'.format(output_directory))           
			else:
				f.write('#SBATCH --output={}/%x-%j.out\n'.format(output_directory))
				f.write('#SBATCH --error={}/%x-%j.err\n\n'.format(output_directory))

		if data_list:
			f.write('#SBATCH --array=0-{}'.format(len(data_list) - 1))
			if array_limit:
				f.write('%{}'.format(array_limit))
			f.write('\n\ndata=({})\n\n'.format(' '.join(data_list)))
			f.write('{}=${{data[$SLURM_ARRAY_TASK_ID]}}\n\n'.format(variable))
			#if variable not in command:
			#	print('Warning: {} not found in {}. Are you sure about this?'.format(variable, command))


		if type(command) is str:
			command = [command]
		f.write('\n')
		f.write('\n'.join(command))

	return filename
		

# notify by email when an existing job finishes
# this is for when you forget to add notification in the first place
def Notify(jobnumber, email, account = None):
	return (WrapSlurmCommand(command = 'echo done', account = account, email=email, dependency=jobnumber, deptype = 'any'))
	
def JobStatus(jobnumber):
	status = []
	for line in JobInfo(jobnumber, ['jobid', 'state'], noheader = True).split('\n'):
		if (line.split() and '+' not in line.split()[0]):
			status.append(line.split())
	return status

default_format = ['jobid','jobname','partition','state','elapsed', 'MaxRss']

def JobInfo(jobnumber, format_list = default_format, noheader = None):
	command = ['sacct','-j',str(jobnumber),'--format', ','.join(format_list)]
	if noheader == True:
		command.append('-n')
	process = subprocess.run(command, stdout=subprocess.PIPE, 
							 stderr=subprocess.STDOUT, universal_newlines=True)
	return(process.stdout)
	

def ShowStatus(jobnumber):
	statuses= [x[1] for x in JobStatus(jobnumber)]
	for x in set(statuses):
		print(x, statuses.count(x))

def AnyJobs(jobnumber, status):
	return status in [x[1] for x in JobStatus(jobnumber)]

def AllJobs(jobnumber, status):
	statuses = set([x[1] for x in JobStatus(jobnumber)])
	if len(statuses) > 1:
		return False
	else:
		return status in statuses


class slurmjob:
	def __init__(self, jobname = None, index = None, 
				email = None,  output_directory = None, dependency = None, deptype = 'ok',
				data_list = None, array_limit = None, variable = 'x',
				threads = None, srun_directory = None, filename = None, **slurm_params):
		
		self.jobname = jobname
		self.command = list()
		self.index = index
		self.email = email
		self.data_list = data_list
		self.variable = variable
		self.output_directory = output_directory
		self.dependency = dependency
		self.threads = threads
		self.array_limit = array_limit
		self.deptype = deptype
		self.jobnumber = None
		self.filename = None
		self.slurm_params = slurm_params

	def AddSlurmParameters(self, **kwargs):
		self.slurm_params.update(kwargs)
		
	def WriteSlurmFile(self, jobname = None, command = list(), filename = None, interpreter = 'bash', 
		**kwargs):

		if jobname:
			self.jobname = jobname		
		if not self.jobname:
			raise ValueError('jobname not set')			
		
		if command:
			self.command = command
		#if not self.command:
		#	raise ValueError('command not set')
		
		if filename:
			self.filename = filename
		else:
			self.filename = '{}.srun'.format(self.jobname)

		
		slurmfile = WriteSlurmFile(jobname = self.jobname, command = self.command, 
			index = self.index, email = self.email, filename = self.filename,
			data_list = self.data_list, variable = self.variable, 
			output_directory = self.output_directory, dependency = self.dependency,
			threads = self.threads, interpreter = interpreter,
			array_limit = self.array_limit, deptype = self.deptype,
			**{**self.slurm_params, **kwargs})

		return slurmfile

	def SubmitSlurmFile(self):
		self.jobnumber = SubmitSlurmFile(self.filename)			
		return self.jobnumber


	## submit command to slurm using "wrap"
	def WrapSlurmCommand(self, command=None, **kwargs):
		if command:
			self.command = command

		self.jobnumber = WrapSlurmCommand(command = self.command, index = self.index, output_directory = self.output_directory, 
			dependency = self.dependency, email = self.email, threads = self.threads, deptype = self.deptype,
			**{**self.slurm_params, **kwargs})

		return self.jobnumber
	

	def GetOutputFiles(self, extension = 'all'):
		if self.output_directory :
			filename = os.path.join(self.output_directory, '{}-{}'.format(self.jobname, self.jobnumber))
		else:
			filename = 'slurm-{}'.format(self.jobnumber)
		if extension == 'all':
			return sorted(glob.glob(filename + '*.*'))
		else:
			return sorted(glob.glob(filename + '*.' + extension))


	def Notify(self, email = None):
		if not email:
			email = self.email
		if not email:
			raise ValueError('no email to notify!')
		return Notify(jobnumber = self.jobnumber, email = email, account = self.account)
	
	def JobStatus(self):
		return JobStatus(self.jobnumber)


	def JobInfo(self, format_list = default_format, noheader = None):
		return JobInfo(self.jobnumber, format_list, noheader)


	def ShowStatus(self):
		return ShowStatus(self.jobnumber)

	def ShowOutput(self, index = 0, extension = 'all'):
		import re
		files = self.GetOutputFiles()
		files_to_show = [x for x in files if not re.search('_[^{}]'.format(index), x)]
		for file in files_to_show:
			print(file)
			with open (file) as f:
				print(f.read())

	def PrintSlurmFile(self):
		with open (self.filename) as f:
			print(f.read())

	def NewCommand(self):
		self.command = list()

	def AppendCommand(self, commandstring):
		self.command.append(commandstring)

	# doing this because I can't remember datalist vs data_list
	def ArrayJob(self, data_list):
		self.data_list = data_list



		
