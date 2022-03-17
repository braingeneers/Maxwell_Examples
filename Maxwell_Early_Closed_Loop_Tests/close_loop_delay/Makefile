CXXFLAGS=-Wno-deprecated-declarations
LDLIBS=-lzmq
EXENAME=close_loop_delay
all: $(EXENAME)

clean:
	rm $(EXENAME)

run: $(EXENAME)
	./$< 100
