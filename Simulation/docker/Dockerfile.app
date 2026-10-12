# Fast application-only rebuild from a previously built native Neptune image.
# Use the full Dockerfile for dependency, renderer or asset changes.
ARG NEPTUNE_BASE=neptune-perception:latest
FROM ${NEPTUNE_BASE}
COPY src/ /opt/neptune/src/
COPY Simulation/config/ /opt/neptune/Simulation/config/
COPY Simulation/scenarios/ /opt/neptune/Simulation/scenarios/
RUN . /opt/ros/jazzy/setup.sh && . /opt/stonefish_ws/install/setup.sh \
    && cd /opt/neptune && colcon build --base-paths src/neptune_sim src/neptune_perception \
    && chmod +x src/tools/*.sh
