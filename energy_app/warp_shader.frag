// From https://stackoverflow.com/questions/33018652#42103766
varying vec2 textureCoordinate;

uniform sampler2D inputImageTexture;

// NOTE: you will need to pass the INVERSE of the homography matrix, as well as
// the width and height of your image as uniforms!
uniform mat3 inverseHomographyMatrix;
uniform float width;
uniform float height;

void main()
{
   // Texture coordinates will run [0,1],[0,1];
   // Convert to "real world" coordinates
   vec3 frameCoordinate = vec3(textureCoordinate.x * width, textureCoordinate.y * height, 1.0);

   // Determine what 'z' is
   vec3 m = inverseHomographyMatrix[2] * frameCoordinate;
   float zed = 1.0 / (m.x + m.y + m.z);
   frameCoordinate = frameCoordinate * zed;

   // Determine translated x and y coordinates
   float xTrans = inverseHomographyMatrix[0][0] * frameCoordinate.x + inverseHomographyMatrix[0][1] * frameCoordinate.y + inverseHomographyMatrix[0][2] * frameCoordinate.z;
   float yTrans = inverseHomographyMatrix[1][0] * frameCoordinate.x + inverseHomographyMatrix[1][1] * frameCoordinate.y + inverseHomographyMatrix[1][2] * frameCoordinate.z;

   // Normalize back to [0,1],[0,1] space
   vec2 coords = vec2(xTrans / width, yTrans / height);

   // Sample the texture if we're mapping within the image, otherwise set color to black
   if (coords.x >= 0.0 && coords.x <= 1.0 && coords.y >= 0.0 && coords.y <= 1.0) {
       gl_FragColor = texture2D(inputImageTexture, coords);
   } else {
       gl_FragColor = vec4(0.0,0.0,0.0,0.0);
   }
   //gl_FragColor = texture2D(inputImageTexture, textureCoordinate);
   //gl_FragColor = vec4(coords,0.0,1.0);
}
