"""Defines the class for a job execution job task"""
from __future__ import unicode_literals

from job.execution.running.tasks.base_task import Task
from job.models import JobExecution
from job.resources import NodeResources


class JobTask(Task):
    """Represents a job execution job task (runs the actual job/algorithm)
    """

    def __init__(self, job_exe):
        """Constructor

        :param job_exe: The job execution, which must be in RUNNING status and have its related node, job, and job_type
        models populated
        :type job_exe: :class:`job.models.JobExecution`
        """

        super(JobTask, self).__init__('%i_job' % job_exe.id, job_exe)

        self._is_system = job_exe.job.job_type.is_system
        self._uses_docker = job_exe.uses_docker()
        if self._uses_docker:
            if self._is_system:
                self._docker_image = self.create_scale_image_name()
            else:
                self._docker_image = job_exe.get_docker_image()
            self._docker_params = job_exe.get_job_configuration().get_job_task_docker_params()
            self._is_docker_privileged = job_exe.is_docker_privileged()
        self._command = job_exe.get_job_interface().get_command()
        self._command_arguments = job_exe.command_arguments

    def complete(self, task_results):
        """See :meth:`job.execution.running.tasks.base_task.Task.complete`
        """

        if self._task_id != task_results.task_id:
            return

        JobExecution.objects.task_ended(self._job_exe_id, 'job', task_results.when, task_results.exit_code)

        return False

    def get_resources(self):
        """See :meth:`job.execution.running.tasks.base_task.Task.get_resources`
        """

        # Input files have already been written, only disk space for output files is required
        return NodeResources(cpus=self._cpus, mem=self._mem, disk=self._disk_out)

    def fail(self, task_results, error=None):
        """See :meth:`job.execution.running.tasks.base_task.Task.fail`
        """

        if self._task_id != task_results.task_id:
            return None

        if not error and self.is_running:
            # If the task successfully started, use job's error mapping here to determine error
            default_error_name = 'unknown' if self._is_system else 'algorithm-unknown'
            error = self._error_mapping.get_error(task_results.exit_code, default_error_name)
        if not error:
            error = self.consider_general_error(task_results)

        JobExecution.objects.task_ended(self._job_exe_id, 'job', task_results.when, task_results.exit_code)

        return error

    def refresh_cached_values(self, job_exe):
        """Refreshes the task's cached job execution values with the given model

        :param job_exe: The job execution model
        :type job_exe: :class:`job.models.JobExecution`
        """

        self._command_arguments = job_exe.command_arguments

    def running(self, when):
        """See :meth:`job.execution.running.tasks.base_task.Task.running`
        """

        super(JobTask, self).running(when)
        JobExecution.objects.task_started(self._job_exe_id, 'job', when)
