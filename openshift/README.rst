##############
Setup:
##############

pfcon could be run with swift and local storage (using hostPath) as backend. We typically use hostPath for testing locally.

Assuming oc cluster up has been run.

.. code-block:: bash

    # Changes for using hostPath in container. These are not needed, if you want to use swift as backend storage.
    mkdir /tmp/share           # Create a directory that could be mounted in container. This is mounted as /share in container.
    chcon -R -t svirt_sandbox_file_t /tmp/share/ # Change selinux label so that containers can read/write from/to directory.
    sudo oc login -u system:admin
    sudo oc edit scc restricted     # Update allowHostDirVolumePlugin to true and runAsUser type to RunAsAny
    # To set the passwords, follow the instructions in the "Setting up authorization" section. Simply editing example-config.cfg DOES NOT DO ANYTHING.
    oc create -f example-secret.yml # Uses the default password ("password")

*************************
Setting up authorization
*************************
1) Edit the configuration file:

.. code-block:: bash
    
    #example-config.cfg
    [AUTH TOKENS]
    examplekey1 = examplepassword1
    examplekey2 = examplepassword2

2) Convert the configuration to base64:

.. code-block:: bash
  
    cat example-config.cfg | base64

3) Place the output in a new file:

.. code-block:: bash
  
    apiVersion: v1
    kind: Secret
    metadata:
      name: pfcon-config
    type: Opaque
    data:
      pfcon_config.cfg: <base64 encoded configuration>

##################################################################
Swift Object Store. (Ignore this section if you are using hostDir)
##################################################################

The OpenStack Object Store project, known as Swift, offers cloud storage software so that you can store and retrieve lots of data with a simple API. It's built for scale and optimized for durability, availability, and concurrency across the entire data set. Swift is ideal for storing unstructured data that can grow without bound. 

To enable Swift Object store option for pfcon, start pfcon with --swift-storage option (this has been already taken care of if you are using the OpenShift template available in this repo).

.. code-block:: bash

    pfcon --forever --httpResponse --swift-storage --createDirsAsNeeded

The pushPath and pullPath operations are same as mentioned for mounting directories method.

The credentials file for Swift should be stored in a **secret**, mounted at /etc/swift in the pod with the name ‘swift-credentials.cfg’. It should contain the swift credentials in the following format:


.. code-block:: bash

    [AUTHORIZATION]
    osAuthUrl          =

    [SECRET]
    applicationId      =
    applicationSecret  =


************************************
Creating a secret and running pfcon.
************************************
1) Create a text file with the name swift-credentials.cfg as shown above (ignore this step if you are running locally).


2) Now run the following command to create a secret (ignore this step if you are running locally).

.. code-block:: bash

    oc create secret generic swift-credentials --from-file=<path-to-file>/swift-credentials.cfg


3) Run pfcon.

.. code-block:: bash

    oc new-app openshift/pfcon-openshift-template.json  # if you are using swift backend
    oc new-app openshift/pfcon-openshift-template-without-swift.json  # if you are using local storage

