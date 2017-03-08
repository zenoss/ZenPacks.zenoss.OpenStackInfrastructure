DISTDIR = ../../dist

docs:
	[ -d $(DISTDIR) ] || mkdir $(DISTDIR)
	pandoc ceilometer.md --template=template.html --table-of-contents > $(DISTDIR)/ceilometer.html
