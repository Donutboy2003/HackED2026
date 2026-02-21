CXX      := g++
CXXFLAGS := -std=c++17 -O2 -Wall -Wextra
LIBS     := -lm
TARGET   := sensor
SRCS     := main.cpp adxl343.cpp
OBJS     := $(SRCS:.cpp=.o)

.PHONY: all clean install

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LIBS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

# Install the binary next to the Python app
install: $(TARGET)
	cp $(TARGET) ../$(TARGET)

clean:
	rm -f $(OBJS) $(TARGET)
