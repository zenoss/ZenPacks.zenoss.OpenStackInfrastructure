default: egg

egg:
	python setup.py bdist_egg

develop:
	python setup.py develop

test:
	find . -name *.pyc -print -exec rm {} \;
	PYTHONPATH="${PYTHONPATH}:`pwd`/sshclient" trial --temp-directory=/tmp/_trial_tmp sshclient.test

clean:
	rm -rf build lib dist *.egg-info
