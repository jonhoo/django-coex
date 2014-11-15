all: z3str/z3str/libz3str.so z3str.py byteplay.py

z3str/z3/Makefile z3str/.git/refs/heads/master: ../.gitmodules
	git submodule update --init -- ./z3str

z3str/z3/bin/external/libz3.so: z3str/z3/Makefile z3str/.git/refs/heads/master
	(cd z3str/z3; autoconf; ./configure)
	make -C z3str/z3 a so
	touch $@

z3str/z3str/libz3str.so: z3str/z3/bin/external/libz3.so
	make -C z3str/z3str
	touch $@

z3str.py: z3str/z3str/z3str.py
	patch -i z3str.patch -o $@ $<

byteplay-upstream.py:
	wget -O $@ https://byteplay.googlecode.com/svn/trunk/byteplay.py

byteplay.py: byteplay-upstream.py byteplay.patch
	patch -i byteplay.patch -o $@ byteplay-upstream.py
