import { readFilesystemSync } from '@electron/asar/lib/disk.js';
const p = '/tmp/v2re/teach/AppName/versions/v1.0.0/resources/app.asar';
const fsys = readFilesystemSync(p);
console.log('headerSize:', fsys.getHeaderSize());
console.log('header keys:', Object.keys(fsys.header.files || {}));
