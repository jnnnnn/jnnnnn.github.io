# Networking in AWS notes

2020-12: I'm an enterprise-networking novice. I'm involved with configuring
XPLAN Radware load balancer to talk to a lambda in AWS. It's proven complicated.
I decided to learn a little about AWS networking. Here are my notes.

https://www.youtube.com/watch?v=hiKPPy584Mg in fast-forward.

2022-07: I've forgotten it all again. I'm involved with granting access to an
RDS for an EC2 instance.

## Basics of VPCs and AWS networking

**VPC** is a virtual data center. Each AWS account has one or, really, is one.
Can be more but rare. Machines/services/instances in a VPC can only talk to
other machines in the VPC by default.

Cider range sounds delicious. it's a group of IP addresses, **CIDR**.
172.16.0.0/16 is 65k addresses. Not internet addresses, 172.x and 10.x are for
private networks.

**Availability zone**: `a`, `b`, or `c`. All about redundancy. Separate power grids,
flood profiles. all inside the default vpc. Traffic inside a particular
availability zone is not charged.

**subnets**, for example `172.31.0.0/24`, are in a particular availability zone. each one
can have different **route tables**.

**route** is a cider range and a destination. so, e.g., to find `172.30.0.0/24`
you may go to target "on-prem-gateway".

for a server in vpc to access internet, it needs:

1. a public IP address -- so put it in the public subnet and it will get one
2. a route to the internet -- so add a route in the subnet config pointing at an
   Internet gateway. `0.0.0.0/0` means allow all.

**private** subnet means the machines don't get a public address, have to access
internet through a NAT gateway (which is set up in the public subnet so it has a
public IP) which only allows outbound connections.

**security group**, "SG", is a firewall. automatically configures for responses so that you
don't have to configure both directions. Allows configuring firewall for all
servers (instances) in the security group.

**NACL**s or "Nackles" (Network Access Control Lists) are security groups for subnets. Very
coarse-grained. Don't automatically configure for responses. Keep them simple or
don't use at all.

**flow logs** can be turned on for instances, subnets, or VPCs and can be used to
debug why your networking settings aren't working. They show origin and
destination IP and port and the result of the packet-sending attempt. don't show
packet payloads (only size).

**DNS** can be automatically provided by the VPC -- both names for instances and
resolution of external names.

**Transit Gateway** connects VPCs together (between accounts). Must not overlap
cider ranges, so that an IP address is not ambiguous and the routers know where
to send packets. May also have to configure routes in your VPC or subnets.

On-prem networking is via VPN or Direct Connect.

**Direct Connect** is a physical connection from on-prem to one or more VPCs. Goes
via an AWS cage in your datacenter -- arrange a port in the AWS router. Better
than VPN because more predictable latency.

VPC **endpoints** let you route to particular services (e.g. S3) without using
public IP addresses.

**PrivateLink** allocates internal IP addresses to external services. Allows talk
between VPCs with overlapping IP addresses.

**Global Accelerator** is for internet-facing applications. It is a way of getting
customer connections onto the AWS backbone as soon as possible to avoid "weather
conditions" on the public internet.
