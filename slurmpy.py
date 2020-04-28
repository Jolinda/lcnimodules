import subprocess
import os
import glob

def OnTalapas():
	groups = subprocess.run(['groups'], stdout = subprocess.PIPE, universal_newlines = True).stdout.strip().split()
	return 'talapas' in groups

def DefaultPirg():
	groups = subprocess.run(['groups'], stdout = subprocess.PIPE, universal_newlines = True).stdout.strip().split()
	pirgs = [x for x in groups if x != 'talapas']
	if 'talapas' in groups and pirgs:
		return pirgs[0]
	else:
		return None


def ValidPirg(pirg):
	if OnTalapas():
		return pirg in os.listdir('/projects')
	else:
		return False

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
def WrapSlurmCommand(command, account = None, index = None, partition = 'short', 
					 output_directory = None, dependency = None, email = None, mem = None, 
					 threads = None, clock_limit = None, deptype = 'ok'):

	if OnTalapas():
		if not account:
			account = DefaultPirg()
			
		if not ValidPirg(account):
			raise ValueError('Unknown pirg: {}'.format(account)) 
	
	slurm = 'sbatch --partition={} '.format(partition)

	slurm += '--account={} '.format(account)
	
	if index:
		slurm += '--comment=idx:{} '.format(index)

	if (partition == 'gpu'):
		slurm += '--gres=gpu:1 '
	
	if email:
		slurm += '--mail-user={} --mail-type=END '.format(email)
		
	if dependency:
		slurm += '--dependency=after{}:{} '.format(deptype, dependency)
		
	if clock_limit: ### Wall clock time limit in Days-HH:MM:SS
		slurm += '--time={} '.format(clock_limit)
		
	if mem:
		slurm += '--mem={} '.format(mem)

	if threads:
		slurm += '--cpus-per-task={} '.format(threads)
		
	if output_directory:
			if not os.path.exists(output_directory):
				os.mkdir(output_directory)
			slurm += '--output={}/%x-%j.out '.format(output_directory)
			slurm += '--error={}/%x-%j.err '.format(output_directory)
		
	slurm += '--wrap \"' + command + '"'
	
	print(slurm)
	process = subprocess.run(slurm, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
								 universal_newlines=True, shell=True)

	print(process.stdout)

	if process.stdout.split()[0] == 'Submitted':
		return process.stdout.split()[-1]
	else :
		return None


def WriteSlurmFile(jobname, command, filename = None, account = None, index = None, partition = 'short', 
				   mem = None, data_list = None, variable = 'x', output_directory = None, dependency = None,
				   threads = None, clock_limit = None, array_limit = None, deptype = 'ok', email = None):
	
	if not filename:
		filename = jobname + '.srun'

	if OnTalapas():
		if not account:
			account = DefaultPirg()
			
		if not ValidPirg(account):
			print ('Warning: unknown pirg: {}'.format(account)) 
	
	with open (filename, 'w') as f:
		f.write('#!/bin/bash\n')
		f.write('#SBATCH --partition={}\n'.format(partition))

		if (partition == 'gpu'):
			 f.write('#SBATCH --gres=gpu:1\n')

		f.write('#SBATCH --job-name={}\n'.format(jobname))
		f.write('#SBATCH --nodes=1\n') 
		f.write('#SBATCH --ntasks=1\n')

		if email:
			f.write('#SBATCH --mail-user={}\n'.format(email))
			f.write('#SBATCH --mail-type=END\n')

		if mem:
			f.write('#SBATCH --mem={}\n'.format(mem))

		if dependency:
			 f.write('#SBATCH --dependency=after{}:{}\n'.format(deptype, dependency))

		if threads:
			f.write('#SBATCH --cpus-per-task={}\n'.format(threads))

		if clock_limit: ### Wall clock time limit in Days-HH:MM:SS
			f.write('#SBATCH --time={}\n'.format(clock_limit))    

		f.write('#SBATCH --comment=idx:{}\n'.format(index))

		f.write('#SBATCH --account={}\n'.format(account))

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
			if '$' + variable not in command:
				print('Warning: ${} not found in {}. Are you sure about this?'.format(variable, command))

		f.write(command + '\n')

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
	def __init__(self, jobname = None, account = None, index = None, command = None, partition = 'short',
				email = None,  output_directory = None, dependency = None, deptype = 'ok',
				clock_limit = None, data_list = None, array_limit = None, variable = 'x',
				threads = None, mem = None, srun_directory = None, filename = None):
		
		self.jobname = jobname
		self.command = command
		if OnTalapas() and not account:
			self.account = DefaultPirg()
		else:
			self.account = account

		self.index = index
		self.partition = partition
		self.email = email
		self.mem = mem
		self.data_list = data_list
		self.variable = variable
		self.output_directory = output_directory
		self.dependency = dependency
		self.threads = threads
		self.clock_limit = clock_limit
		self.array_limit = array_limit
		self.deptype = deptype
		self.__jobnumber = None
		self.filename = None
		
	def WriteSlurmFile(self, jobname = None, command = None, filename = None):	
		if jobname:
			self.jobname = jobname		
		if not self.jobname:
			raise ValueError('jobname not set')			
		
		if command:
			self.command = command
		if not self.command:
			raise ValueError('command not set')
		
		if filename:
			self.filename = filename
		else:
			self.filename = '{}.srun'.format(self.jobname)


		
		slurmfile = WriteSlurmFile(jobname = self.jobname, command = self.command, account = self.account, 
			index = self.index, partition = self.partition, email = self.email, filename = self.filename,
			mem = self.mem, data_list = self.data_list, variable = self.variable, 
			output_directory = self.output_directory, dependency = self.dependency,
			threads = self.threads, clock_limit = self.clock_limit, 
			array_limit = self.array_limit, deptype = self.deptype)

		return slurmfile

	def SubmitSlurmFile(self):
		self.__jobnumber = SubmitSlurmFile(self.filename)			
		return self.__jobnumber


	## submit command to slurm using "wrap"
	def WrapSlurmCommand(self, command=None):
		if command:
			self.command = command

		self.__jobnumber = WrapSlurmCommand(command = self.command, account = self.account, 
			index = self.index, partition = self.partition, output_directory = self.output_directory, 
			dependency = self.dependency, email = self.email, mem = self.mem, 
			threads = self.threads, clock_limit = self.clock_limit, deptype = self.deptype)

		return self.__jobnumber
	

	def GetOutputFiles(self, extension = 'all'):
		if self.output_directory :
			filename = os.path.join(self.output_directory, '{}-{}'.format(self.jobname, self.__jobnumber))
		else:
			filename = 'slurm-{}'.format(self.__jobnumber)
		if extension == 'all':
			return sorted(glob.glob(filename + '*.*'))
		else:
			return sorted(glob.glob(filename + '*.' + extension))
		
