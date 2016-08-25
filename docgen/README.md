# Welcome to FreeNAS X CLI Documentation Generator!

The docgen requires live FreeNAS10 instance to connect to, therefore the credentials must be provided when generating
the documentation.

Run command:

make IP=<freenas.machine.ip> USER=<username> PASS=<password> [O=<optional.output.path>]

The results will be available at : ./cli.docs if the 'O' parameter was not specified.
