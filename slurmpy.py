"""module to assist in SLURM job submission

This module was developed to assist with SLURM job submission on the 
talapas high performance computing cluser at the University of Oregon.
"""

import subprocess
import os
import glob
import time
import re
import sys

default_format = ['jobid%15','jobname%30','partition','state','elapsed', 
    'MaxRss']
"""default format for job display in JobInfo
"""

def OnTalapas():
    """are we currently on talapas?
    """
    groups = subprocess.run(['groups'], stdout = subprocess.PIPE, universal_newlines = True).stdout.strip().split()
    return 'talapas' in groups


def SlurmThrottle():
    """call Mike Coleman's slurm-throttle script

    This command will sleep until the user has fewer than 500 jobs queued in
    SLURM.

    The idea is that instead of running an sbatch and having it die due to
    hitting the enqueued job limit, the user can use this command to sleep 
    until there are plenty of open slots, and immediately after run their 
    sbatch command, which will then (almost certainly) not hit the limit.

    """
    subprocess.run(['/packages/racs/bin/slurm-throttle'])

def SubmitSlurmFile(filename):
    """ submit a file to slurm using sbatch

    Submits a file to slurm using sbatch, and prints the stdout from the
    sbatch command

    Parameters
    ----------
    filename: path to file

    Returns
    -------
    jobid if successful
    None if file not found
    """

    if not os.path.exists(filename):
        print('{} not found'.format(filename))
        return None
    process = subprocess.run(['sbatch', filename], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.STDOUT, 
                             universal_newlines=True)

    print(process.stdout)

    if process.stdout.split()[0] == 'Submitted':
        jobid = process.stdout.split()[-1]
    else :
        jobid = None
            
    return jobid


def WaitUntilComplete(jobid):
    """wait until job completes.

    Parameters
    ----------
    jobid: slurm job id of job to monitor
    """

    time.sleep(10)
    while True:
        if not AnyJobs(jobid, 'PENDING') and not AnyJobs(jobid, 'RUNNING'):
            if AllJobs(jobid,'COMPLETED'):
                print('Job complete')
                return
            else:
                print(JobStatus(jobid))
                assert False

        if AnyJobs(jobid, 'PENDING'):
            queue = subprocess.run('squeue', stdout=subprocess.PIPE, 
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
            for line in queue.split('\n'):
                if jobid in line and 'ReqNodeNotAvail' in line:
                    print(line)
                    assert False

        time.sleep(10)

def WrapSlurmCommand(command, jobname = None, index = None, 
                     output_directory = None, dependency = None, 
                     email = None, threads = None, deptype = 'ok', 
                     **slurm_params):

    """submit command to slurm using sbatch --wrap

    Parameters
    ----------
    command: str or list[str]
        command or list of commands to submit
    jobname: str, optional
        name to give job, if not including jobname will be 'wrap'
    threads: int or int string
        number of threads to used, identical to --cpus-per-task
    email: str, optional
        email address for --mail-user notification
    dependency: int or string, optional
        defer start of job until dependency compltes
    deptype: str, default = 'ok'
        only used if dependency is set
        how the parent job must end. may be ok, any, burstbuffer,
        notok, corr. See sbatch documentation for more info.
    output_directory: path string, optional
        directory to write {jobname}.out/{jobname}.err files to
        directory will be created if it doesn't exist
    index: str, optional
        UO index for charges, will be written to comment field
    **slurm_params: dict
        additional slurm parameters

    Returns
    -------
    slurm jobid if successful, None if not

    Examples
    --------
    >>> WrapSlurmCommand('echo hello')

    >>> WrapSlurmCommand(['module load fsl', 'fslinfo somefile'],
                         jobname = 'example',
                         email = 'mymail@someaddress.com',
                         account = 'lcni',
                         partition = 'short')

     >>> WrapSlurmCommand(['module load fsl', 'fslinfo somefile'],
                         jobname = 'example',
                         **{'partition': 'short',
                            'account': 'lcni',
                            'tasks-per-cpu': 1})    

    You must use the last example's format when defining slurm 
    parameters containing dashes                  
    
    """ 
    

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


def WriteSlurmFile(jobname, command, filename = None, 
                   interpreter = 'bash', index = None,  
                   array = None, variable = 'x', 
                   output_directory = None, dependency = None,
                   threads = None, array_limit = None, deptype = 'ok', 
                   email = None, **slurm_params):
    
    """Write a script to be submitted to slurm using sbatch

    Parameters
    ----------
    jobname: str
        name to give job
    command: str or list[str]
        command or list of commands to run
    filename: str, optional
        name for script file, will be jobname.srun if not given
    interpreter: str, optional
        path to interpreter
        if 'bash' (default), will use /bin/bash
    threads: int or int string, optional
        number of threads to used, identical to --cpus-per-task
    email: str, optional
        email address for --mail-user notification
    dependency: int or string, optional
        defer start of job until dependency compltes
    deptype: str, default = 'ok'
        only used if dependency is set
        how the parent job must end. may be ok, any, burstbuffer,
        notok, corr. See sbatch documentation for more info.
    output_directory: path string, optional
        directory to write {jobname}.out/{jobname}.err files to
        directory will be created if it doesn't exist
    index: str, optional
        UO index for charges, will be written to comment field
    array: list, optional
        array to use for job array
    variable: string, default = 'x'
        variable to use for array substitution in command
    array-limit: int
        maximum number of concurrently running tasks
        NOT CURRENTLY IMPLEMENTED
    **slurm_params: dict
        additional slurm parameters

    Returns
    -------
    filename of slurm script

    Examples
    --------
    >>> WriteSlurmFile('example', 'echo hello')
    example.srun

    >>> WriteSlurmFile('fslinfo',
                        ['module load fsl', 'fslinfo somefile'],
                        jobname = 'fslinfo',
                        email = 'mymail@someaddress.com',
                        account = 'lcni',
                        partition = 'short')
    fslinfo.srun

    >>> WriteSlurmFile('fslinfo', 
                        ['module load fsl', 'fslinfo ${x}'],
                        filename = 'fslinfo_array.srun'
                        jobname = 'fslinfo',
                        array = ['file1', 'file2', 'file3'],
                        account = 'lcni')
    fslinfo_array.srun

    >>> WriteSlurmFile('fslinfo',
                        ['module load fsl', 'fslinfo somefile'],
                        **{'partition': 'short',
                           'account': 'lcni',
                           'tasks-per-cpu': 1})    

    You must use the last example's format when defining slurm 
    parameters containing dashes                  
    
    """

    if not filename:
        filename = jobname + '.srun'

    with open (filename, 'w') as f:
        if interpreter == 'python':
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
            if array:
                f.write('#SBATCH --output={}/%x-%A_%a.out\n'.format(output_directory))
                f.write('#SBATCH --error={}/%x-%A_%a.err\n\n'.format(output_directory))           
            else:
                f.write('#SBATCH --output={}/%x-%j.out\n'.format(output_directory))
                f.write('#SBATCH --error={}/%x-%j.err\n\n'.format(output_directory))

        if array:
            f.write('#SBATCH --array=0-{}'.format(len(array) - 1))
            if array_limit:
                f.write('%{}'.format(array_limit))
            f.write('\n\ndata=({})\n\n'.format(' '.join(array)))
            f.write('{}=${{data[$SLURM_ARRAY_TASK_ID]}}\n\n'.format(variable))
            #if variable not in command:
            #   print('Warning: {} not found in {}. Are you sure about this?'.format(variable, command))


        if type(command) is str:
            command = [command]
        f.write('\n')
        f.write('\n'.join(command))

    return filename
        

def Notify(jobid, email, **kwargs):
    """notify by email when an existing job finishes

     This is for when you forget to add notification in the first place.
     It creates a job that depends on the first job and sends a 
     notification when it finishes.

     Parameters
     ---------
     jobid
        jobid for the job you want to be notified about
     email
        where the notification should be sent
     **kwargs
        option keyword arguments for WrapSlurmCommands

     Returns
     -------
     jobid of echo done command

     """
    return (WrapSlurmCommand(command = 'echo done', email=email, 
                             dependency=jobid, deptype = 'any', 
                             **kwargs))
    
def JobStatus(jobid):
    """return status(es) of job

    Parameter
    ---------
    jobid
        id of job

    Returns
    -------
    list
        state of each job in array

    """

    status = []
    for line in JobInfo(jobid, ['jobid', 'state'], noheader = True).split('\n'):
        if (line.split() and '+' not in line.split()[0]):
            status.append(line.split())
    return status



def JobInfo(jobid, format_list = default_format, noheader = None):
    """ returns information about job. Use with print().

    Parameters
    ----------
    jobid
        id of job

    format_list: optional
        format to use with sacct

    noheader: bool, optional
        include header in output

    Returns
    -------
    stdout from !sacct command.
    """

    command = ['sacct','-j',str(jobid),'--format', 
               ','.join(format_list)]
    if noheader == True:
        command.append('-n')
    process = subprocess.run(command, stdout=subprocess.PIPE, 
                             stderr=subprocess.STDOUT, 
                             universal_newlines=True)
    return(process.stdout)
    

def ShowStatus(jobid):
    """ print status of job (condensed)
    """
    statuses= [x[1] for x in JobStatus(jobid)]
    for x in set(statuses):
        print(x, statuses.count(x))

def AnyJobs(jobid, status):
    return status in [x[1] for x in JobStatus(jobid)]

def AllJobs(jobid, status):
    statuses = set([x[1] for x in JobStatus(jobid)])
    if len(statuses) > 1:
        return False
    else:
        return status in statuses


class SlurmJob:
    """ class defining a slurm job

    Attributes
    ----------
    jobname, optional
        name to give job
    command, optional
        command to execute
    filename: str, optional
        name for script file, will be jobname.srun if not given
    threads: int or int string, optional
        number of threads to used, identical to --cpus-per-task
    email: str, optional
        email address for --mail-user notification
    dependency: int or string, optional
        defer start of job until dependency compltes
    deptype: str, default = 'ok'
        only used if dependency is set
        how the parent job must end. may be ok, any, burstbuffer,
        notok, corr. See sbatch documentation for more info.
    output_directory: path string, optional
        directory to write {jobname}.out/{jobname}.err files to
        directory will be created if it doesn't exist
    index: str, optional
        UO index for charges, will be written to comment field
    array: list, optional
        array to use for job array
    variable: string, default = 'x'
        variable to use for array substitution in command
    array-limit: int
        maximum number of concurrently running tasks
        NOT CURRENTLY IMPLEMENTED
    **slurm_params: dict
        additional slurm parameters

    """
    def __init__(self, jobname = None, index = None, command = list(),
                email = None,  output_directory = None, 
                dependency = None, deptype = 'ok',
                array = None, array_limit = None, variable = 'x',
                threads = None, **slurm_params):
        
        self.jobname = jobname
        self.command = command
        self.index = index
        self.email = email
        self.array = array
        self.variable = variable
        self.output_directory = output_directory
        self.dependency = dependency
        self.threads = threads
        self.array_limit = array_limit
        self.deptype = deptype
        self.jobid = None
        self.filename = None
        self.slurm_params = slurm_params

    def AddSlurmParameters(self, **kwargs):
        """add slurm parameter to class

        Example
        -------
        sj = slurmpy.SlurmJob()
        sj.AddSlurmParameter(account = 'lcni', mem = '16G')
        sj.AddSlurmParameter(**{'comment':'test', 'tasks-per-cpu': 1})

        """
        self.slurm_params.update(kwargs)
        
    def WriteSlurmFile(self, filename = None, interpreter = 'bash'):

        """Write a script to be submitted to slurm using sbatch

        Parameters
        ----------
        filename: str, optional
            name for script file, will be jobname.srun if not given
        interpreter: str, optional
            path to interpreter
            if 'bash' (default), will use /bin/bash

        Returns
        -------
        filename of slurm script

"""
        if not self.jobname:
            raise ValueError('jobname not set')         
             
        if filename:
            self.filename = filename
        else:
            self.filename = '{}.srun'.format(self.jobname)

        
        slurmfile = WriteSlurmFile(jobname = self.jobname, 
            command = self.command, index = self.index, 
            email = self.email, filename = self.filename,
            array = self.array, variable = self.variable, 
            output_directory = self.output_directory, 
            dependency = self.dependency, deptype = self.deptype,
            threads = self.threads, interpreter = interpreter,
            array_limit = self.array_limit,
            **self.slurm_params)

        return slurmfile

    def SubmitSlurmFile(self):
        self.jobid = SubmitSlurmFile(self.filename)         
        return self.jobid


    ## submit command to slurm using "wrap"
    def WrapSlurmCommand(self):

        self.jobid = WrapSlurmCommand(command = self.command, 
            index = self.index, 
            output_directory = self.output_directory, 
            dependency = self.dependency, email = self.email, 
            threads = self.threads, deptype = self.deptype,
            **self.slurm_params)

        return self.jobid
    

    def GetOutputFiles(self, extension = 'all'):
        if self.output_directory :
            filename = os.path.join(self.output_directory, 
                '{}-{}'.format(self.jobname, self.jobid))
        else:
            filename = 'slurm-{}'.format(self.jobid)
        if extension == 'all':
            return sorted(glob.glob(filename + '*.*'))
        else:
            return sorted(glob.glob(filename + '*.' + extension))


    def Notify(self, email = None):
        if not email:
            email = self.email
        if not email:
            raise ValueError('no email to notify!')
        return Notify(jobid = self.jobid, email = email, 
            account = self.account)
    
    def JobStatus(self):
        return JobStatus(self.jobid)


    def JobInfo(self, format_list = default_format, noheader = None):
        return JobInfo(self.jobid, format_list, noheader)


    def ShowStatus(self):
        return ShowStatus(self.jobid)

    def ShowOutput(self, index = 0, extension = 'all'):

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





        
