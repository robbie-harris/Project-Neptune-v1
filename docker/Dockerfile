FROM ros:jazzy-ros-base-noble

ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=jazzy

SHELL ["/bin/bash", "-lc"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    git \
    curl \
    python3-pip \
    python3-venv \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool \
    ros-jazzy-vision-msgs \
    ros-jazzy-cv-bridge \
    python3-opencv \
    mesa-utils \
    libgl1-mesa-dri \
    libgl1-mesa-dev \
    libglm-dev \
    libsdl2-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

RUN echo "source /opt/ros/jazzy/setup.bash" >> /root/.bashrc

CMD ["bash"]

# Stonefish marine simulator library
COPY external/stonefish /opt/stonefish

# Project Neptune Stonefish FLS compatibility patch.
# Reduces the FLS compute workgroup from 64 -> 16 threads and
# updates the matching dispatch size for WSL2/D3D12 stability.
COPY docker/stonefish_overrides/Library/shaders/flsOutput.comp \
     /opt/stonefish/Library/shaders/flsOutput.comp
COPY docker/stonefish_overrides/Library/src/graphics/OpenGLFLS.cpp \
     /opt/stonefish/Library/src/graphics/OpenGLFLS.cpp

RUN cmake \
      -S /opt/stonefish \
      -B /opt/stonefish/build \
      -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /opt/stonefish/build --parallel 8 \
    && cmake --install /opt/stonefish/build \
    && ldconfig

# Stonefish ROS 2 wrapper
RUN mkdir -p /opt/stonefish_ws/src

COPY external/stonefish_ros2 /opt/stonefish_ws/src/stonefish_ros2

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
         libpcl-dev \
    && source /opt/ros/jazzy/setup.bash \
    && cd /opt/stonefish_ws \
    && rosdep update \
    && rosdep install \
         --from-paths src \
         --ignore-src \
         --rosdistro jazzy \
         --skip-keys pcl \
         -r -y \
    && colcon build \
         --symlink-install \
         --cmake-args -DCMAKE_BUILD_TYPE=Release \
    && rm -rf /var/lib/apt/lists/*

RUN echo "source /opt/stonefish_ws/install/setup.bash" >> /root/.bashrc

# WSL2/Stonefish graphics compatibility:
# Mesa 25.x causes Stonefish shader-link failures through WSLg D3D12.
# Mesa 24.0.5 renders correctly on the Neptune RTX 4080 setup.
RUN apt-get update \
    && apt-get install -y --allow-downgrades \
       libgl1-mesa-dri=24.0.5-1ubuntu1 \
       libglx-mesa0=24.0.5-1ubuntu1 \
       libegl-mesa0=24.0.5-1ubuntu1 \
       libgbm1=24.0.5-1ubuntu1 \
       libglapi-mesa=24.0.5-1ubuntu1 \
       libgl1-mesa-dev=24.0.5-1ubuntu1 \
    && apt-mark hold \
       libgl1-mesa-dri \
       libglx-mesa0 \
       libegl-mesa0 \
       libgbm1 \
       libglapi-mesa \
       libgl1-mesa-dev \
    && rm -rf /var/lib/apt/lists/*
