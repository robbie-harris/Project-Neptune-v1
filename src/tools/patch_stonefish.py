#!/usr/bin/env python3
"""Apply Neptune's narrowly scoped clock patch to pinned upstream sources.

The simulator remains paced by wall time; sensor messages use physical simulation
seconds. Vision callbacks share the previous render's timestamp (PBO readback).
Upstream files retain their GPL headers. Fail on source drift rather than guessing.
"""
from pathlib import Path
import sys
sf, ros = map(Path, sys.argv[1:])
def replace(path, old, new, count=1):
 text=path.read_text()
 if text.count(old)!=count: raise RuntimeError(f'Upstream drift: {path}: {old[:60]!r}')
 path.write_text(text.replace(old,new))
h=sf/'Library/include/graphics/OpenGLPipeline.h'
# Public getter for the frame being delivered during drawing-queue copy.
replace(h,'GLuint getScreenTexture();','GLuint getScreenTexture();\n        Scalar getCaptureTime() const { return neptuneCaptureTime; }')
replace(h,'Scalar lastSimTime;', 'Scalar lastSimTime;\n        Scalar neptuneCaptureTime = 0;')
p=sf/'Library/src/graphics/OpenGLPipeline.cpp'
replace(p,'Scalar now = sim->getSimulationTime();', 'neptuneCaptureTime = lastSimTime;\n    Scalar now = sim->getSimulationTime();')
# Upstream schedules one non-continuous view per render; render all pending
# views together so stereo pairs are captured from a common scene snapshot.
replace(p,'    //Loop through all views -> trackballs, cameras, depth cameras...',
    '    updateCount = viewsQueue.size();\n    viewsNoUpdate.clear();\n    //Loop through all views -> trackballs, cameras, depth cameras...')
# Clear-water milestone: omit the decorative suspended-particle effect.
replace(p,'glOcean->DrawParticles(camera);','/* Neptune clear-water milestone: particles disabled. */')

# Pause/scheduling gaps must not turn into hours of physics catch-up. Preserve
# the 100 Hz fixed integration step, while bounding catch-up to 100 ms.
replace(sf/'Library/src/core/SimulationManager.cpp',
    '    StepSimulation((Scalar)deltaTime/Scalar(1000000.0));',
    '    if(deltaTime > 100000) deltaTime = 100000; // Neptune bounded catch-up\n    StepSimulation((Scalar)deltaTime/Scalar(1000000.0));')

# Upstream enable services normally start instruments off. The ideal rig starts on.
replace(ros/'src/stonefish_ros2/ROS2ScenarioParser.cpp',
    'sens->setEnabled(false); // Sensor with an enable service starts as disabled',
    'sens->setEnabled(true); // Neptune ideal rig starts with all instruments enabled')

manager=ros/'src/stonefish_ros2/ROS2SimulationManager.cpp'
text=manager.read_text()
text=text.replace('#include "stonefish_ros2/ROS2SimulationManager.h"','#include "stonefish_ros2/ROS2SimulationManager.h"\n#include <Stonefish/core/GraphicalSimulationApp.h>\n#include <Stonefish/graphics/OpenGLPipeline.h>\n#include <chrono>\n#include <thread>\n#include "rosgraph_msgs/msg/clock.hpp"')
# A ROS/system clock adjustment must never underflow unsigned elapsed time.
old='''    rclcpp::Time now = nh_->get_clock()->now(); // Using nh_->get_clock()->now() is WRONG beacause use_sim_time will not work!
    return now.nanoseconds()/1000;'''
if text.count(old)!=1: raise RuntimeError('Upstream simulation clock drift')
text=text.replace(old,'''    return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());''')
old='''    rclcpp::Duration duration(0, (uint32_t)us*1000);
    nh_->get_clock()->sleep_for(duration);'''
if text.count(old)!=1: raise RuntimeError('Upstream simulation sleep drift')
text=text.replace(old,'    std::this_thread::sleep_for(std::chrono::microseconds(us));')
start=text.index('void ROS2SimulationManager::SimulationStepCompleted')
text=text[:start]+text[start:].replace('nh_->get_clock()->now()', 'rclcpp::Time(static_cast<int64_t>(getSimulationTime()*1e9))')
text=text.replace('(void)timeStep; // Suppress warning','''(void)timeStep; // Suppress warning
    if (pubs_.find("neptune_clock") == pubs_.end())
        pubs_["neptune_clock"] = nh_->create_publisher<rosgraph_msgs::msg::Clock>("/clock", 10);
    rosgraph_msgs::msg::Clock clock;
    clock.clock = rclcpp::Time(static_cast<int64_t>(getSimulationTime()*1e9));
    std::static_pointer_cast<rclcpp::Publisher<rosgraph_msgs::msg::Clock>>(pubs_.at("neptune_clock"))->publish(clock);''')
# Vision readbacks all belong to the same previous render cycle.
start=text.index('void ROS2SimulationManager::ColorCameraImageReady')
end=text.index('void ROS2SimulationManager::RespawnRobotService')
chunk=text[start:end].replace('getSimulationTime()*1e9', 'static_cast<GraphicalSimulationApp*>(SimulationApp::getApp())->getGLPipeline()->getCaptureTime()*1e9')
text=text[:start]+chunk+text[end:]
manager.write_text(text)
interface=ros/'src/stonefish_ros2/ROS2Interface.cpp'
text=interface.read_text().replace('nh_->get_clock()->now()', 'rclcpp::Time(static_cast<int64_t>(SimulationApp::getApp()->getSimulationManager()->getSimulationTime()*1e9))')
interface.write_text(text)
c=ros/'CMakeLists.txt'
replace(c,'find_package(rclcpp REQUIRED)', 'find_package(rclcpp REQUIRED)\nfind_package(rosgraph_msgs REQUIRED)')
replace(c,'ament_target_dependencies(stonefish_ros2_interface\n rclcpp', 'ament_target_dependencies(stonefish_ros2_interface\n rosgraph_msgs\n rclcpp')
pkg=ros/'package.xml'; replace(pkg,'<depend>rclcpp</depend>', '<depend>rclcpp</depend>\n  <depend>rosgraph_msgs</depend>')
print('Applied simulation clock and shared render timestamp patch.')
