PREFIX ?= $(HOME)/.local
.PHONY: test install

test:
	python3 -m unittest discover -s tests -v

install:
	install -d "$(DESTDIR)$(PREFIX)/bin"
	install -m 755 bin/config-baseline "$(DESTDIR)$(PREFIX)/bin/config-baseline"
