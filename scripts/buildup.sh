#!/bin/sh

config="configs/kube-tools/gateway/config.json"
routing="configs/kube-tools/gateway/routing.json"

az storage blob download --account-name stazureks --container-name build-resources --name $config --file config.json
az storage blob download --account-name stazureks --container-name build-resources --name $routing --file routing.json

cp config.json services/gateway
cp routing.json services/gateway
