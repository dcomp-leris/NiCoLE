from socket import *

sock = socket(AF_INET, SOCK_DGRAM)

sock.bind(("0.0.0.0", 9999))

print("Waiting for ECN/DSCP signals...")

while True:
    data, addr = sock.recvfrom(1024)

    msg = data.decode()

    dscp, ecn = msg.split(",")

    print(f"Received -> DSCP={dscp}, ECN={ecn}")

    # Example logic
    if int(ecn) == 3:
        print("Congestion Experienced!")