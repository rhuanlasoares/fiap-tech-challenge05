#!bin/bash

cd apps/ngo-service
docker build -t southamerica-east1-docker.pkg.dev/ces-igniteprogram/artreg-ngo/ngo-service .
docker push southamerica-east1-docker.pkg.dev/ces-igniteprogram/artreg-ngo/ngo-service

cd ../donation-service
docker build -t southamerica-east1-docker.pkg.dev/ces-igniteprogram/artreg-donation/donation-service .
docker push southamerica-east1-docker.pkg.dev/ces-igniteprogram/artreg-donation/donation-service

cd ../volunteer-service
docker build -t southamerica-east1-docker.pkg.dev/ces-igniteprogram/artreg-volunteer/volunteer-service .
docker push southamerica-east1-docker.pkg.dev/ces-igniteprogram/artreg-volunteer/volunteer-service
