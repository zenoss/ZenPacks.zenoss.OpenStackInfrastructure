DISTDIR = ../dist
LOCAL_OUTPUT_HTML = $(DISTDIR)/openstackinfrastructure_local.html
OUTPUT_HTML = $(DISTDIR)/openstackinfrastructure.html
default: test

docs:
	[ -d $(DISTDIR) ] || mkdir $(DISTDIR)
	pandoc header.md --template=template.html > $(LOCAL_OUTPUT_HTML)
	pandoc releases.md --template=template.html >> $(LOCAL_OUTPUT_HTML)
	pandoc body.md --template=template.html --table-of-contents >> $(LOCAL_OUTPUT_HTML)
	# pandoc body.md -f markdown_strict --template=template.html --table-of-contents >> $(LOCAL_OUTPUT_HTML)
	cp $(LOCAL_OUTPUT_HTML) $(OUTPUT_HTML)
	perl -p -i -e 's@../docs/images/@https://www.zenoss.com/sites/default/files/zenpack/OpenStack%20(Provider%20View)/@g' $(OUTPUT_HTML)

	make -C kb

test: docs
	echo "<meta charset=\"utf-8\"/>" > /tmp/osi.html
	cat $(LOCAL_OUTPUT_HTML) >> /tmp/osi.html
	cp -a images /tmp/
	perl -p -i -e 's@../docs/images/@images/@g' /tmp/osi.html
