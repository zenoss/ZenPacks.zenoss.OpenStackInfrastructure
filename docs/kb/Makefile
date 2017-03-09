DISTDIR = ../../dist

docs:
	[ -d $(DISTDIR) ] || mkdir $(DISTDIR)
	pandoc header.md --template=template.html > $(DISTDIR)/ceilometer.html
	pandoc ceilometer.md --template=template.html --table-of-contents >> $(DISTDIR)/ceilometer.html
