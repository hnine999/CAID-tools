# webgme-depi
### Installation
Install node/npm on your machine [NodeJS](https://nodejs.org/en/) (LTS recommended)

Install node-modules (root of this repo)
```
npm install
```

Start mongodb:
Either install using instructions here: [MongoDB](https://www.mongodb.com/) or with docker:

```
docker run --name webgme-mongo -d -p 27017:27017 mongo
```

### Start webgme server
Make sure mongodb is running, then from root-dir start webgme-server first:

```
npm start
```

then start the webhook-manager:

```
npm run monitor
```