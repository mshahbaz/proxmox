from pebble import process
import fabric.api as fab
import pve

print fab.env.hosts

fab.env.hosts = ['128.112.168.26']
fab.env.user = 'root'
fab.env.password = 'PrincetonP4OVS1'
fab.env.warn_only = True
fab.env["poweredge_name"] = 'mshahbaz-poweredge-1-pve'
# fab.env['vm_ssh_key'] = '/root/ssh/httperf_id_rsa'
fab.env['vm_ssh_passwd'] = 'nopass'


# Settings

settings = {
    'vms': {
        'base_vm_id': 105,
        # 'clients': [110]
        'clients': [110, 111, 112, 113, 114, 115, 116, 117, 118, 119]
    },
    'httperf': {
        'vip': '12.12.12.101',
        'port': 80,
        'num-conns': 4000,
        'rate': 1000,
        'ramp': 100,
        'iters': 10,
        'timeout': 1,
        'csv-file': 'httperf-log.csv'
    }
}


def generate_client(base_vm_id, vm_id):
    pve.generate_vm(base_vm_id, vm_id, 'feedbackd-client'+str(vm_id), True)


def destroy_client(vm_id):
    pve.destroy_vm(vm_id)


def configure_client(vm_id):
    pve.ssh_run(vm_id, "sudo apt-get install git httperf")
    pve.ssh_run(vm_id, "git clone https://github.com/mshahbaz/httperf-plot.git")


def setup_clients():
    for vm_id in settings['vms']['clients']:
        generate_client(settings['vms']['base_vm_id'], vm_id)
        configure_client(vm_id)


def destroy_clients():
    for vm_id in settings['vms']['clients']:
        destroy_client(vm_id)


@process.spawn(daemon=True)
def run_httperf_client(vm_id):
    if int(pve.ssh_run(vm_id, 'netstat -t | wc -l')) > 100:
        fab.abort("too many TCP connections opened (client:%s)" % (vm_id,))
    fab.local('rm -f results/httperf_client_%s.log' % (vm_id,))
    fab.local('rm -f results/httperf_client_%s.csv' % (vm_id,))
    pve.ssh_run(vm_id,
                "cd ~/httperf-plot;"
                "python httperf-plot.py --server %s --port %s "
                "--hog --num-conns %s --num-calls 1 --rate %s "
                "--ramp-up %s,%s --timeout %s "
                "--csv %s;"
                "cd ~/"
                % (settings['httperf']['vip'], settings['httperf']['port'],
                   settings['httperf']['num-conns'], settings['httperf']['rate'],
                   settings['httperf']['ramp'], settings['httperf']['iters'], settings['httperf']['timeout'],
                   settings['httperf']['csv-file']),
                "/tmp/httperf_client_%s.log" % (vm_id,))
    pve.scp_get(vm_id,
                "~/httperf-plot/%s" % (settings['httperf']['csv-file'],), "/tmp/httperf_client_%s.csv" % (vm_id,))
    fab.get("/tmp/httperf_client_%s.log" % (vm_id,), "results/")
    fab.get("/tmp/httperf_client_%s.csv" % (vm_id,), "results/")
    pve.ssh_run(vm_id, "rm -f ~/httperf-plot/%s" % (settings['httperf']['csv-file'],))
    fab.run("rm -f /tmp/httperf_client_%s.log" % (vm_id,))
    fab.run("rm -f /tmp/httperf_client_%s.csv" % (vm_id,))


def run():
    runs = []
    for vm_id in settings['vms']['clients']:
        runs.append({
            'run': run_httperf_client(vm_id),
            'vm_id': vm_id})
    for i in range(len(runs)):
        runs[i]['run'].join()