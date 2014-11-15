# Eventually, this could be used to start the zoobar application, run tests,
# etc.

.PHONY: all
all:
	make -C symex

.PHONY: clean
clean:
	make -C symex clean
