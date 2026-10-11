ARG BASE_IMAGE=ros:jazzy
FROM ${BASE_IMAGE}
ARG STONEFISH_REV=b21eb8e194c570ff2f61e91aeffb38d73dc25f42
ARG STONEFISH_ROS2_REV=6646e7ac25eed982f37f807abc7b545dbd2d6648
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-jazzy-desktop ros-dev-tools ros-jazzy-vision-msgs ros-jazzy-cv-bridge \
    ros-jazzy-launch-testing ros-jazzy-launch-testing-ros ros-jazzy-rosgraph-msgs \
    python3-pip python3-venv python3-numpy python3-yaml python3-pytest \
    git build-essential cmake libsdl2-dev libfreetype6-dev libglm-dev \
    libgl1-mesa-dri libglx-mesa0 mesa-utils xvfb x11vnc novnc websockify openbox \
    && rm -rf /var/lib/apt/lists/*
# Reuse an existing compatible image when supplied, but check exact source revisions.
RUN if [ ! -d /opt/stonefish/.git ]; then git clone https://github.com/patrykcieslak/stonefish.git /opt/stonefish; fi \
    && git -C /opt/stonefish checkout ${STONEFISH_REV} \
    && mkdir -p /opt/stonefish_ws/src \
    && if [ ! -d /opt/stonefish_ws/src/stonefish_ros2/.git ]; then git clone https://github.com/patrykcieslak/stonefish_ros2.git /opt/stonefish_ws/src/stonefish_ros2; fi \
    && git -C /opt/stonefish_ws/src/stonefish_ros2 checkout ${STONEFISH_ROS2_REV}
COPY src/tools/patch_stonefish.py /tmp/patch_stonefish.py
RUN python3 /tmp/patch_stonefish.py /opt/stonefish /opt/stonefish_ws/src/stonefish_ros2 \
    && cmake -S /opt/stonefish -B /opt/stonefish/build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /opt/stonefish/build -j4 && cmake --install /opt/stonefish/build \
    && . /opt/ros/jazzy/setup.sh \
    && rosdep update && rosdep install --from-paths /opt/stonefish_ws/src --ignore-src --skip-keys pcl -r -y \
    && cd /opt/stonefish_ws && colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
COPY config/requirements.txt /tmp/requirements.txt
RUN python3 -m venv --system-site-packages /opt/neptune-venv \
    && /opt/neptune-venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
COPY . /opt/neptune
RUN . /opt/ros/jazzy/setup.sh && . /opt/stonefish_ws/install/setup.sh \
    && cd /opt/neptune && colcon build --base-paths src/neptune_sim src/neptune_perception \
    && chmod +x src/tools/*.sh
ENV DISPLAY=:1 LIBGL_ALWAYS_SOFTWARE=1 MESA_GL_VERSION_OVERRIDE=4.5 MESA_GLSL_VERSION_OVERRIDE=450
ENV PYTHONPATH=/opt/neptune-venv/lib/python3.12/site-packages
ENV PATH=/opt/neptune-venv/bin:$PATH
ENV YOLO_CONFIG_DIR=/workspace/outputs/ultralytics
WORKDIR /workspace
ENTRYPOINT ["/opt/neptune/src/tools/container-entrypoint.sh"]
CMD ["ros2", "launch", "neptune_sim", "pipe_tank.launch.py"]
