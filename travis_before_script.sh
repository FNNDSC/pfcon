#!/bin/bash

set -ev
chmod -R 755 $(pwd)
mkdir -p FS/remote
chmod -R 777 FS
export STOREBASE=$(pwd)/FS/remote
