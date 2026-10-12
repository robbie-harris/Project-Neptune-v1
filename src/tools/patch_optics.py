#!/usr/bin/env python3
"""Neptune optical controls v1, checked against pinned Stonefish sources.

GL updates occur only in Render; ROS requests never mutate graphics state.
Upstream copyright/license headers are retained.
"""
from pathlib import Path
import sys
sf,ros=map(Path,sys.argv[1:])
def edit(path,old,new,count=1):
    text=path.read_text()
    if text.count(old)!=count: raise RuntimeError(f'Optics upstream drift: {path}: {old[:60]}')
    path.write_text(text.replace(old,new))
h=sf/'Library/include/graphics/OpenGLAtmosphere.h'
edit(h,'    public:', '    public:\n        void SetNaturalLighting(bool on);')
edit(h,'        GLuint sunSkyUBO;', '        GLuint sunSkyUBO;\n        GLuint neptuneNaturalUBO;')
p=sf/'Library/src/graphics/OpenGLAtmosphere.cpp'
edit(p,'    memset(&sunSkyUBOData, 0, sizeof(SunSkyUBO));', '''    memset(&sunSkyUBOData, 0, sizeof(SunSkyUBO));
    // Binding zero is unused by the pinned upstream UBO constants (1..4).
    glGenBuffers(1, &neptuneNaturalUBO);
    glBindBuffer(GL_UNIFORM_BUFFER, neptuneNaturalUBO);
    GLfloat natural[4] = {1.f,0.f,0.f,0.f};
    glBufferData(GL_UNIFORM_BUFFER, sizeof(natural), natural, GL_DYNAMIC_DRAW);
    glBindBufferBase(GL_UNIFORM_BUFFER, 0, neptuneNaturalUBO);
    glBindBuffer(GL_UNIFORM_BUFFER, 0);''')
edit(p,'void OpenGLAtmosphere::SetupMaterialShaders()', '''void OpenGLAtmosphere::SetNaturalLighting(bool on)
{
    GLfloat natural[4] = {on ? 1.f : 0.f,0.f,0.f,0.f};
    glBindBuffer(GL_UNIFORM_BUFFER, neptuneNaturalUBO);
    glBufferSubData(GL_UNIFORM_BUFFER, 0, sizeof(natural), natural);
    glBindBuffer(GL_UNIFORM_BUFFER, 0);
}

void OpenGLAtmosphere::SetupMaterialShaders()''')
edit(p,'    glDeleteBuffers(1, &sunSkyUBO);','    glDeleteBuffers(1, &sunSkyUBO);\n    glDeleteBuffers(1, &neptuneNaturalUBO);')
g=sf/'Library/shaders/atmosphereApi.glsl'
edit(g,'#inject "atmosphere.glsl"', '#inject "atmosphere.glsl"\nlayout (std140) uniform NeptuneOptics { float neptuneNaturalLight; };')
s=g.read_text()
for line in list(s.splitlines()):
    if 'return ' in line and ('GetSkyRadiance' in line or 'atmosphere.solar_irradiance' in line):
        s=s.replace(line,line.replace('return ','return neptuneNaturalLight * '))
s=s.replace('return GetSunAndSkyIrradiance(atmosphere, transmittance_texture, irradiance_texture, p, normal, sun_direction, sky_irradiance);',
'''IrradianceSpectrum sun = GetSunAndSkyIrradiance(atmosphere, transmittance_texture, irradiance_texture, p, normal, sun_direction, sky_irradiance);
    sky_irradiance *= neptuneNaturalLight;
    return sun * neptuneNaturalLight;''')
s=s.replace('sky_irradiance *= SKY_SPECTRAL_RADIANCE_TO_LUMINANCE;', 'sky_irradiance *= SKY_SPECTRAL_RADIANCE_TO_LUMINANCE * neptuneNaturalLight;')
s=s.replace('return sun_irradiance * SUN_SPECTRAL_RADIANCE_TO_LUMINANCE;', 'return sun_irradiance * SUN_SPECTRAL_RADIANCE_TO_LUMINANCE * neptuneNaturalLight;')
g.write_text(s)
p=sf/'Library/src/graphics/GLSLShader.cpp'
edit(p,'    glLinkProgram(program);\n#ifdef DEBUG', '''    glLinkProgram(program);
    GLuint neptuneBlock = glGetUniformBlockIndex(program, "NeptuneOptics");
    if (neptuneBlock != GL_INVALID_INDEX) glUniformBlockBinding(program, neptuneBlock, 0);
// Neptune retains link diagnostics in release builds.''')
edit(p,'#endif\n    glGetProgramiv(program, GL_LINK_STATUS, &programLinked);','    glGetProgramiv(program, GL_LINK_STATUS, &programLinked);')
h=sf/'Library/include/graphics/OpenGLPipeline.h'
edit(h,'#include <deque>','#include <deque>\n#include <mutex>')
edit(h,'        GLuint getScreenTexture();','''        GLuint getScreenTexture();
        void RequestNeptuneOptics(const std::vector<double>& values) {
            std::lock_guard<std::mutex> guard(neptuneOpticsMutex); neptuneRequested = values;
        }
        std::vector<double> GetNeptuneOptics() {
            std::lock_guard<std::mutex> guard(neptuneOpticsMutex); return neptuneApplied;
        }''')
edit(h,'        Scalar neptuneCaptureTime = 0;','''        Scalar neptuneCaptureTime = 0;
        std::mutex neptuneOpticsMutex;
        std::vector<double> neptuneRequested{0,1,1,.02,0};
        std::vector<double> neptuneApplied{-1,1,1,.02,0,0};''')
p=sf/'Library/src/graphics/OpenGLPipeline.cpp'
edit(p,'#include <algorithm>','#include <algorithm>\n#include "actuators/Light.h"')
edit(p,'    Atmosphere* atm = sim->getAtmosphere();','''    Atmosphere* atm = sim->getAtmosphere();
    {
        std::lock_guard<std::mutex> guard(neptuneOpticsMutex);
        if (neptuneRequested[0] != neptuneApplied[0]) {
            auto left = dynamic_cast<Light*>(sim->getActuator("Neptune/LightLeft"));
            auto right = dynamic_cast<Light*>(sim->getActuator("Neptune/LightRight"));
            bool ok = ocean && atm && left && right;
            if (ok) {
                ocean->setWaterType(neptuneRequested[3]);
                ocean->setParticles(neptuneRequested[4] != 0);
                atm->getOpenGLAtmosphere()->SetNaturalLighting(neptuneRequested[1] != 0);
                left->Switch(neptuneRequested[2] != 0);
                right->Switch(neptuneRequested[2] != 0);
            }
            neptuneApplied = neptuneRequested;
            neptuneApplied.push_back(ok ? 1 : 0);
        }
    }''')
edit(p,'/* Neptune clear-water milestone: particles disabled. */', 'if (ocean->hasParticles()) glOcean->DrawParticles(camera);')
m=ros/'src/stonefish_ros2/ROS2SimulationManager.cpp'
edit(m,'#include <chrono>','#include <chrono>\n#include <cmath>\n#include <sstream>\n#include <Stonefish/entities/StaticEntity.h>')
edit(m,'    // Standard services','''    pubs_["neptune_optics"] = nh_->create_publisher<std_msgs::msg::Float64MultiArray>("/neptune/optics/applied", 10);
    subs_["neptune_optics"] = nh_->create_subscription<std_msgs::msg::Float64MultiArray>(
        "/neptune/optics/request", 10, [this](const std_msgs::msg::Float64MultiArray::SharedPtr msg) {
            const auto& v=msg->data;
            if (v.size()!=5) return;
            for (double n:v) if (!std::isfinite(n)) return;
            if (v[0]<1 || (v[1]!=0 && v[1]!=1) || (v[2]!=0 && v[2]!=1)
                || v[3]<0 || v[3]>1 || (v[4]!=0 && v[4]!=1)) return;
            static_cast<GraphicalSimulationApp*>(SimulationApp::getApp())->getGLPipeline()->RequestNeptuneOptics(v);
        });
    auto retained = rclcpp::QoS(1).transient_local();
    pubs_["neptune_instances"] = nh_->create_publisher<std_msgs::msg::String>("/neptune/capture/instance_map", retained);
    std::ostringstream map;
    map << "{";
    bool comma=false;
    for (const auto& name : {"Pipeline", "InspectionValve", "InspectionFlange"}) {
        auto ent=dynamic_cast<StaticEntity*>(getEntity(name));
        if (!ent) continue;
        for (const auto& renderable:ent->Render()) {
            if (renderable.objectId<0) continue;
            if (comma) map << ",";
            comma=true;
            map << "\\\"" << renderable.objectId+1 << "\\\":\\\"" << name << "\\\"";
        }
    }
    map << "}";
    std_msgs::msg::String mapping; mapping.data=map.str();
    std::static_pointer_cast<rclcpp::Publisher<std_msgs::msg::String>>(pubs_["neptune_instances"])->publish(mapping);
    if (auto capture=getSensor("Neptune/CaptureInstances")) capture->setEnabled(false);
    if (auto overview=getSensor("TankOverview")) {
        srvs_["neptune_overview_enable"] = nh_->create_service<std_srvs::srv::SetBool>(
            "/neptune/sensors/TankOverview/set_enabled",
            std::bind(&ROS2SimulationManager::SensorService, this, _1, _2, overview));
    }
    // Standard services''')
edit(m,'    (void)timeStep; // Suppress warning','''    auto optics = static_cast<GraphicalSimulationApp*>(SimulationApp::getApp())->getGLPipeline()->GetNeptuneOptics();
    if (pubs_.count("neptune_optics")) {
        std_msgs::msg::Float64MultiArray applied; applied.data=optics;
        std::static_pointer_cast<rclcpp::Publisher<std_msgs::msg::Float64MultiArray>>(pubs_["neptune_optics"])->publish(applied);
    }
    (void)timeStep; // Suppress warning''')
print('Applied Neptune optical controls v1 and offline instance metadata.')
