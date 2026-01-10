AIC8800 USB WiFi Driver
=======================

This is a Debian package for the AIC8800 USB WiFi adapters.

The original source, under GPL v2, is from:

https://linux.brostrend.com/troubleshooting/source-code/

This source is a little bit weird, because the most reliable upstream
package for these sources is, itself, a Debian package. However, that
package requires some changes to be well-behaved. Those changes are
included here.

Updating the Upstream Source Tarball
------------------------------------

You can rebuild or update the upstream source tarball:

    wget https://linux.brostrend.com/aic8800-dkms.deb -O ../aic8800-dkms.deb
    dpkg-deb --fsys-tarfile ../aic8800-dkms.deb | xz > ../aic8800_$VER.orig.tar.xz

The contents of this current directory contain the modified sources,
which are used by the Debian package tools to create a patch to the
upstream sources. If upstream makes changes, you can do the same to
port these changes over to the new upstream version.

Forgive me, this made the most sense at the time.
