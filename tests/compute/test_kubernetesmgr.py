"""
Unit tests for KubernetesManager.create_job focused on volume mount
construction and label formatting. These cover regressions around
issue FNNDSC/pfcon#162 (sub_path missing for copy/delete jobs) and
the k8s-idiomatic label key `chrisproject.org/job-type`.

These tests do not require a live cluster: kubernetes.config loading
is mocked and only the in-memory V1Job is built via create_job.
"""
import unittest
from unittest import mock


class TestKubernetesManagerCreateJob(unittest.TestCase):

    def _make_manager(self, config=None):
        from pfcon.compute.kubernetesmgr import KubernetesManager

        cfg = {'VOLUME_NAME': 'storebase-pvc'}
        if config:
            cfg.update(config)

        with mock.patch(
                'pfcon.compute.kubernetesmgr.k_config.load_incluster_config'), \
             mock.patch(
                'pfcon.compute.kubernetesmgr.k_client.CoreV1Api'), \
             mock.patch(
                'pfcon.compute.kubernetesmgr.k_client.BatchV1Api'):
            return KubernetesManager(cfg)

    def _resources(self):
        return {
            'number_of_workers': 1,
            'cpu_limit': 1000,
            'memory_limit': 300,
            'gpu_limit': 0,
        }

    def _get_vol_mounts(self, job):
        return job.spec.template.spec.containers[0].volume_mounts

    def test_output_mount_has_sub_path(self):
        """Regression for #162: outputdir_source must translate to
        V1VolumeMount.sub_path so copy/delete workers see job files."""
        mgr = self._make_manager()
        mounts = {
            'inputdir_source': None,
            'inputdir_target': '/share/incoming',
            'outputdir_source': 'key-jid-1',
            'outputdir_target': '/share/outgoing',
        }
        job = mgr.create_job(
            'img', ['python'], 'jid-1-delete', self._resources(),
            [], None, None, mounts
        )

        vms = self._get_vol_mounts(job)
        outmount = next(vm for vm in vms if vm.mount_path == '/share/outgoing')
        self.assertEqual(outmount.sub_path, 'key-jid-1')
        self.assertEqual(outmount.name, 'storebase')

    def test_inputdir_none_means_no_mount(self):
        """inputdir_source=None => no input volume mount."""
        mgr = self._make_manager()
        mounts = {
            'inputdir_source': None,
            'inputdir_target': '/share/incoming',
            'outputdir_source': 'key-jid-2',
            'outputdir_target': '/share/outgoing',
        }
        job = mgr.create_job(
            'img', ['python'], 'jid-2-upload', self._resources(),
            [], None, None, mounts
        )

        vms = self._get_vol_mounts(job)
        self.assertFalse(
            any(vm.mount_path == '/share/incoming' for vm in vms)
        )

    def test_inputdir_empty_string_mounts_volume_root(self):
        """Regression: fslink copy passes inputdir_source='' meaning
        mount whole PVC root. The input mount must be present with no
        sub_path (sub_path=None)."""
        mgr = self._make_manager()
        mounts = {
            'inputdir_source': '',
            'inputdir_target': '/share/incoming',
            'outputdir_source': 'key-jid-3',
            'outputdir_target': '/share/outgoing',
        }
        job = mgr.create_job(
            'img', ['python'], 'jid-3-copy', self._resources(),
            [], None, None, mounts
        )

        vms = self._get_vol_mounts(job)
        inmount = next(
            (vm for vm in vms if vm.mount_path == '/share/incoming'), None
        )
        self.assertIsNotNone(inmount, 'input mount must be present')
        self.assertIsNone(inmount.sub_path, 'must mount PVC root, no sub_path')
        self.assertEqual(inmount.name, 'storebase')

    def test_inputdir_subpath(self):
        """Non-empty inputdir_source => sub_path on the input mount."""
        mgr = self._make_manager()
        mounts = {
            'inputdir_source': 'key-jid-4/incoming',
            'inputdir_target': '/share/incoming',
            'outputdir_source': 'key-jid-4',
            'outputdir_target': '/share/outgoing',
        }
        job = mgr.create_job(
            'img', ['python'], 'jid-4', self._resources(),
            [], None, None, mounts
        )

        vms = self._get_vol_mounts(job)
        inmount = next(vm for vm in vms if vm.mount_path == '/share/incoming')
        self.assertEqual(inmount.sub_path, 'key-jid-4/incoming')

    def test_job_type_label_uses_k8s_convention(self):
        """Kubernetes label key must be `chrisproject.org/job-type`,
        not the docker-style `org.chrisproject.job_type`."""
        mgr = self._make_manager()
        mounts = {
            'inputdir_source': None,
            'inputdir_target': '/share/incoming',
            'outputdir_source': 'key-jid-5',
            'outputdir_target': '/share/outgoing',
        }
        job = mgr.create_job(
            'img', ['python'], 'jid-5-copy', self._resources(),
            [], None, None, mounts,
            extra_labels={'job_type': 'copy'}
        )
        labels = job.spec.template.metadata.labels
        self.assertIn('chrisproject.org/job-type', labels)
        self.assertEqual(labels['chrisproject.org/job-type'], 'copy')
        self.assertNotIn('org.chrisproject.job_type', labels)
        self.assertNotIn('job_type', labels)


if __name__ == '__main__':
    unittest.main()
