#!/bin/bash

cd apps/ngo-service
docker build -t southamerica-east1-docker.pkg.dev/ces-igniteprogram/artreg-ngo-sa/ngo-service .
docker push southamerica-east1-docker.pkg.dev/ces-igniteprogram/artreg-ngo-sa/ngo-service

cd ../donation-service
docker build -t southamerica-east1-docker.pkg.dev/ces-igniteprogram/artreg-donation-sa/donation-service .
docker push southamerica-east1-docker.pkg.dev/ces-igniteprogram/artreg-donation-sa/donation-service

cd ../volunteer-service
docker build -t southamerica-east1-docker.pkg.dev/ces-igniteprogram/artreg-volunteer-sa/volunteer-service .
docker push southamerica-east1-docker.pkg.dev/ces-igniteprogram/artreg-volunteer-sa/volunteer-service

cd ../gcp-status-checker
docker build -t southamerica-east1-docker.pkg.dev/ces-igniteprogram/artreg-status/gcp-status-checker .
docker push southamerica-east1-docker.pkg.dev/ces-igniteprogram/artreg-status/gcp-status-checker