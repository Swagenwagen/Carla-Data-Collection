import numpy
import carla
from datetime import datetime
import os
import time
import queue

from GenerateBoundingBoxes import GenerateBoundingBoxes
from Vehicle import *

# set up world
client = carla.Client('localhost', 2000)

world = client.get_world()

# set world to synchronous
settings = world.get_settings()

settings.synchronous_mode = True

world.apply_settings(settings)

# get spawn points and blueprints
spawn_points = world.get_map().get_spawn_points()

# set up blueprints
blueprint_library = world.get_blueprint_library()

# code to get spectator position; useful for spawning vehicles where you are in the simulator. Must disable synchronous mode to work (just comment out the code)
# i = 0
# while i < 30:
#     print(world.get_spectator().get_transform())
#     i += 1
#     time.sleep(1)

# enable traffic manager
tm = client.get_trafficmanager()

# set up camera attached to ego vehicle
camera_blueprint = blueprint_library.find('sensor.camera.rgb')

camera_transform = carla.Transform(carla.Location(z=2))

# set up lidar sensor attached to ego vehicle
lidar_blueprint = blueprint_library.find("sensor.lidar.ray_cast")

# note, the settings below caused carla to be unstable on my system
# lidar_blueprint.set_attribute('channels', '64')
# lidar_blueprint.set_attribute('points_per_second', '100000')
# lidar_blueprint.set_attribute('rotation_frequency', '10')
# lidar_blueprint.set_attribute('range',str(20))

lidar_transform = carla.Transform(carla.Location(z=2))

# spawn ego vehicle
vehicle_blueprint = blueprint_library.filter('model3')[0]

vehicle_spawn_point = carla.Transform(carla.Location(x=43.78, y=27.83, z=5))

ego_vehicle = EgoVehicle(world, vehicle_blueprint, vehicle_spawn_point, tm)
ego_vehicle.add_sensor('camera', camera_blueprint, camera_transform)
ego_vehicle.add_sensor('lidar', lidar_blueprint, lidar_transform)
ego_vehicle.enable_driving()

# generate 2 dummy vehicles at intersection
dummy_vehicle = Vehicle(world, vehicle_blueprint, carla.Transform(carla.Location(x=101.774811, y=12.668145, z=5)), tm)
dummy_vehicle2 = Vehicle(world, vehicle_blueprint, carla.Transform(carla.Location(x=104.068077, y=-3.374074, z=2.768713)), tm)

# # Note, code below was unstable on my machine. Probably a ram limitation
# # generate 4 sensors at intersection
# # generate 2 cameras
# int_sensor1_transform = carla.Transform(carla.Location(x=114.093, y=29.769, z=5.853), carla.Rotation(yaw=180))
# int_sensor2_transform = carla.Transform(carla.Location(x=104.236, y=22.047, z=5.853), carla.Rotation(yaw=135))

# int_cam1 = world.spawn_actor(camera_blueprint, int_sensor1_transform)
# int_cam2 = world.spawn_actor(camera_blueprint, int_sensor2_transform)

# int_cam1_queue = queue.Queue()
# int_cam2_queue = queue.Queue()

# int_cam1.listen(int_cam1_queue.put)
# int_cam2.listen(int_cam2_queue.put)

# #generate two lidar sensors
# int_lidar1 = world.spawn_actor(lidar_blueprint, int_sensor1_transform)
# int_lidar2 = world.spawn_actor(lidar_blueprint, int_sensor2_transform)

# int_lidar1_queue = queue.Queue()
# int_lidar2_queue = queue.Queue()

# int_lidar1.listen(int_lidar1_queue.put)
# int_lidar2.listen(int_lidar2_queue.put)

# enable sensor on ego vehicle
ego_vehicle.enable_sensor_queue('camera')
ego_vehicle.enable_sensor_queue('lidar')

# generate camera matrix
camera_matrix = numpy.array(ego_vehicle.sensors['camera'].get_transform().get_inverse_matrix())

# generate projection matrix from camera intrinsics
image_w = camera_blueprint.get_attribute("image_size_x").as_int()
image_h = camera_blueprint.get_attribute("image_size_y").as_int()
fov = camera_blueprint.get_attribute("fov").as_float()

projection_matrix = GenerateBoundingBoxes.build_projection_matrix(image_w, image_h, fov)

def checkForBoundingBoxes(actor_name, ego_actor):
    # loop through all vehicles in world
    for npc in world.get_actors().filter('*vehicle*'):
        # check if vehicle isn't the same as ego actor
        if npc.id != ego_actor.id:
            # confirm npc vehicle is within 50 meters
            dist = npc.get_transform().location.distance(ego_actor.get_transform().location)
            if dist < 50:
                # determine if vehicle is in front of the camera
                forward_vec = ego_actor.get_transform().get_forward_vector()
                ray = npc.get_transform().location - ego_actor.get_transform().location
                if forward_vec.dot(ray) > 1:
                    # open file
                    bounding_box_path = os.path.abspath(".\\bounding boxes.txt")
                    print(bounding_box_path)
                    f = open(bounding_box_path, 'a')
                    
                    # write 3d and 2d bounding boxes seen from ego_actor to file
                    Bounding_Boxes = GenerateBoundingBoxes(npc, projection_matrix, camera_matrix)
                    f.write('3D Bounding Box from view of ' + actor_name + ': ' + str(Bounding_Boxes.build3dBoundingBox()) + '\n')
        
                    x_max, x_min, y_max, y_min = Bounding_Boxes.build2dBoundingBox()
                    if x_min > 0 and x_max < image_w and y_min > 0 and y_max < image_h: 
                        f.write(f'2D Bounding Box from view of ' + actor_name + ': ' + str([x_max, x_min, y_max, y_min]) + '\n')
                    
                    f.close()

# set up file system
os.chdir("..\\")

# start server tick
tick = 0

while True:
    world.tick()

    if (tick % 10 == 0):
        # get current date and time
        current_date_time = datetime.now().strftime("%m-%d-%Y, %H-%M-%S")

        # change directory to sub folder
        path = os.path.abspath(".\\") + f"\\{current_date_time}"
        os.mkdir(path)
        os.chdir(path)

        # save ego vehicle camera image
        camera_path = os.path.abspath(".\\CAMERA")
        image = ego_vehicle.get_sensor_queue('camera').get()
        image.save_to_disk(camera_path)

        # save ego vehicle lidar data
        lidar_path = os.path.abspath(".\\LIDAR")
        lidar = ego_vehicle.get_sensor_queue('lidar').get()
        lidar.save_to_disk(lidar_path)

        # # Sensors below disabled due to memory issues
        # # save intersection camera data
        # int_camera1_path = os.path.abspath(".\\INT_CAMERA1")
        # int_camera2_path = os.path.abspath(".\\INT_CAMERA1")
        # int_cam1_image = int_cam1_queue.get()
        # int_cam2_image = int_cam2_queue.get()
        # int_cam1_image.save_to_disk(int_camera1_path)
        # int_cam2_image.save_to_disk(int_camera2_path)

        # # save intersection lidar data
        # int_camera1_path = os.path.abspath(".\\INT_CAMERA1")
        # int_camera2_path = os.path.abspath(".\\INT_CAMERA1")
        # int_cam1_image = int_cam1_queue.get()
        # int_cam2_image = int_cam2_queue.get()
        # int_cam1_image.save_to_disk(int_camera1_path)
        # int_cam2_image.save_to_disk(int_camera2_path)

        # get camera matrix
        camera_matrix = numpy.array(ego_vehicle.sensors['camera'].get_transform().get_inverse_matrix())
        
        # loop through all vehicles in world
        checkForBoundingBoxes("ego_vehicle", ego_vehicle())
        # # Not checking bounding boxes on sensors below due to ram issues
        # checkForBoundingBoxes("int_camera1", int_cam1)
        # checkForBoundingBoxes("int_camera1", int_cam1)
    
        os.chdir("..\\")

    tick += 1
