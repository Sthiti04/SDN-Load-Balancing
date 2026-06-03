from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel

class LoadBalancerTopo(Topo):
    def build(self):
        # Add switch
        switch = self.addSwitch('s1')
        
        # Add 1 client
        client = self.addHost('h1',ip='10.0.0.1/24')

        # Add 4 server hosts
        self.addLink(client, switch)
        server_ips = ['10.0.0.2','10.0.0.3','10.0.0.4','10.0.0.5']
        for i, ip in enumerate(server_ips, start=2):
            server = self.addHost(f'h{i}', ip=f'{ip}/24')
            self.addLink(server, switch)

        # Connect client to switch
       
topos = {
    'mytopo': (lambda: LoadBalancerTopo())
}


if __name__ == '__main__':
    setLogLevel('info')
    topo = LoadBalancerTopo()
    net = Mininet(topo=topo, controller=RemoteController)
    net.start()
    print("Custom topology with 1 client and 4 server hosts")
    CLI(net)
    net.stop()