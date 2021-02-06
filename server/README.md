# Overview [![Docker Image Status][docker-image]][docker] [![License][license-image]][license]

Cognitive assistant for making a sandwich out of parts from
[this](https://web.archive.org/web/20160122145218/https://www.amazon.com/Small-World-Toys-Living-Sandwich/dp/B00004W156)
kit. Watch a demo video
[here](https://www.youtube.com/watch?v=USakPP45WvM). If you do not have the toy
sandwich kit, you can test the assistant using
[these](https://docs.google.com/document/d/e/2PACX-1vRgMkNs4dGd5dsyR4_BadXYY9UKfLz3W8Ah11sfkauuHSW10tWMpZo7vm0HEMwSJV-LBXGp7ICIU5E4/pub)
images. See
[here](https://docs.google.com/drawings/d/15wmevFqD2FE_dqVGJI0EU3L5igNC6SEnNhNdw40KNkI)
for this assistant's states and transitions.

[docker-image]: https://img.shields.io/docker/build/cmusatyalab/gabriel-sandwich.svg
[docker]: https://hub.docker.com/r/cmusatyalab/gabriel-sandwich

[license-image]: http://img.shields.io/badge/license-Apache--2-blue.svg?style=flat
[license]: LICENSE

# Installation

## Client

An Android client is available on
[Google Play](https://play.google.com/store/apps/details?id=edu.cmu.cs.gabrielclient).
The source code is available
[here](https://github.com/cmusatyalab/gabriel-instruction/tree/master/android).

## Server

Running the server application using Docker is advised. If you want to run the
code directly, please see our [Dockerfile](Dockerfile) for details.

# How to Run

## Client

Add servers by name and IP/domain from the main activity. This activity also
contains a toggle to show subtitles with instructions. Subtitles are useful for
devices that may not have integrated speakers (such as the ODG R-7). Connect to
a server by pressing the button to the left of its name.

## Server

### Container

```bash
docker run --rm -it --gpus all -p 9099:9099 cmusatyalab/gabriel-sandwich:latest
```
