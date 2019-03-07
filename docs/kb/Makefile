DISTDIR = ../../dist

# Publish to https://support.zenoss.com/hc/en-us/articles/115001165446-Understanding-and-Troubleshooting-OpenStack-Ceilometer-Integration-with-Zenoss-Resource-Manager

docs:
	[ -d $(DISTDIR) ] || mkdir $(DISTDIR)
	pandoc header.md --template=template.html > $(DISTDIR)/ceilometer.html
	pandoc ceilometer.md --template=template.html --table-of-contents >> $(DISTDIR)/ceilometer.html
	cp $(DISTDIR)/ceilometer.html /tmp/ceilometer.html
