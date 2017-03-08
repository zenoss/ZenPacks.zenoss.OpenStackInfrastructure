DISTDIR = ../dist
OUTPUT_HTML = $(DISTDIR)/openstackinfrastructure.html

docs:
	[ -d $(DISTDIR) ] || mkdir $(DISTDIR)
	pandoc header.md --template=template.html > $(OUTPUT_HTML)
	pandoc releases.md --template=template.html >> $(OUTPUT_HTML)
	pandoc body.md --template=template.html --table-of-contents >> $(OUTPUT_HTML)
	make -C kb
