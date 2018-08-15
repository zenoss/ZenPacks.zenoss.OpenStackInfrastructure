DISTDIR = ../dist
LOCAL_OUTPUT_HTML = $(DISTDIR)/openstackinfrastructure_local.html
OUTPUT_HTML = $(DISTDIR)/openstackinfrastructure.html

docs:
	[ -d $(DISTDIR) ] || mkdir $(DISTDIR)
	pandoc header.md --template=template.html > $(LOCAL_OUTPUT_HTML)
	pandoc releases.md --template=template.html >> $(LOCAL_OUTPUT_HTML)
	pandoc body.md --template=template.html >> $(LOCAL_OUTPUT_HTML)

	# build a version with the right links for the public site
	cp $(LOCAL_OUTPUT_HTML) $(OUTPUT_HTML)
	perl -p -i -e 's@../docs/images/@https://www.zenoss.com/sites/default/files/zenpack/OpenStack%20(Provider%20View)/@g' $(OUTPUT_HTML)

	make -C kb
