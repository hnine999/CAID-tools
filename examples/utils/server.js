// Minimal server for testing accessibility between machines on a network.

const http = require('http');
const os = require('os');
const port = process.env.PORT || 8000;

const networkIfs = os.networkInterfaces();
const addresses = [];
for (let netId in networkIfs) {
    networkIfs[netId].forEach(network => {
        if (network.family === 'IPv4') {
            addresses.push('http://' + network.address + ':' + port);
        }
    });
}

http.createServer((req, res) => {
    res.writeHead(200, { "Content-Type": "text/plain" });
    res.write("Hello, world!");
    res.end();
}).listen(port, () => {
    console.log('Valid addresses of web server: ', addresses.join('  '));
});