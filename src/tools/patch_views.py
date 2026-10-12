#!/usr/bin/env python3
"""Native view priorities v1. Apply after the pinned Neptune optics patch."""
from pathlib import Path
import sys
sf,ros=map(Path,sys.argv[1:])
def edit(path,old,new):
    text=path.read_text()
    if text.count(old)!=1:raise RuntimeError('View patch source drift: '+str(path))
    path.write_text(text.replace(old,new))
h=sf/'Library/include/graphics/OpenGLPipeline.h'
if 'RequestNeptuneViews' in h.read_text():
    print('Neptune view priorities v1 already installed');raise SystemExit(0)
edit(h,'        Scalar getCaptureTime() const', '''        void RequestNeptuneViews(const std::vector<double>& values) {
            std::lock_guard<std::mutex> guard(neptuneOpticsMutex); neptuneViewsRequested=values;
        }
        std::vector<double> GetNeptuneViews() {
            std::lock_guard<std::mutex> guard(neptuneOpticsMutex); return neptuneViewsApplied;
        }
        std::vector<double> neptuneViewsRequested{0,1,1};
        std::vector<double> neptuneViewsApplied{-1,1,1,0};
        Scalar getCaptureTime() const''')
p=sf/'Library/src/graphics/OpenGLPipeline.cpp'
edit(p,'#include "actuators/Light.h"','#include "actuators/Light.h"\n#include "sensors/Sensor.h"')
edit(p,'        if (neptuneRequested[0] != neptuneApplied[0]) {', '''        if (neptuneViewsRequested[0] != neptuneViewsApplied[0]) {
            bool camera=neptuneViewsRequested[1]!=0, overview=neptuneViewsRequested[2]!=0;
            auto left=sim->getSensor("Neptune/CameraLeft");
            auto right=sim->getSensor("Neptune/CameraRight");
            auto down=sim->getSensor("Neptune/CameraDown");
            auto sonar=sim->getSensor("Neptune/Sonar");
            auto tank=sim->getSensor("TankOverview");
            bool ok=left && right && down && sonar && tank;
            if (ok) {
                bool both=camera && overview;
                left->setUpdateFrequency(camera ? 10 : 5);
                right->setUpdateFrequency(camera ? 10 : 5);
                down->setUpdateFrequency(both ? 10 : 2);
                sonar->setUpdateFrequency(both ? 10 : 2);
                tank->setUpdateFrequency(camera ? 5 : 10);
                tank->setEnabled(overview);
            }
            neptuneViewsApplied=neptuneViewsRequested;
            neptuneViewsApplied.push_back(ok ? 1 : 0);
        }
        if (neptuneRequested[0] != neptuneApplied[0]) {''')
m=ros/'src/stonefish_ros2/ROS2SimulationManager.cpp'
edit(m,'    // Standard services', '''    pubs_["neptune_views"] = nh_->create_publisher<std_msgs::msg::Float64MultiArray>("/neptune/views/applied", 10);
    subs_["neptune_views"] = nh_->create_subscription<std_msgs::msg::Float64MultiArray>(
        "/neptune/views/request",10,[this](const std_msgs::msg::Float64MultiArray::SharedPtr msg) {
            const auto& v=msg->data;
            if (v.size()!=3 || !std::isfinite(v[0]) || v[0]<1
                || (v[1]!=0 && v[1]!=1) || (v[2]!=0 && v[2]!=1)) return;
            static_cast<GraphicalSimulationApp*>(SimulationApp::getApp())->getGLPipeline()->RequestNeptuneViews(v);
        });
    // Standard services''')
edit(m,'    (void)timeStep; // Suppress warning', '''    auto views=static_cast<GraphicalSimulationApp*>(SimulationApp::getApp())->getGLPipeline()->GetNeptuneViews();
    if (pubs_.count("neptune_views")) {
        std_msgs::msg::Float64MultiArray applied;applied.data=views;
        std::static_pointer_cast<rclcpp::Publisher<std_msgs::msg::Float64MultiArray>>(pubs_.at("neptune_views"))->publish(applied);
    }
    (void)timeStep; // Suppress warning''')
print('Applied native Neptune view priorities v1')
