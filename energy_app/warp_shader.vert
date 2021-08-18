// From https://stackoverflow.com/questions/33018652#42103766
attribute vec4 vertex;

varying vec2 textureCoordinate;

void main() {
   // Nothing happens in the vertex shader
   textureCoordinate = vertex.zw;
   gl_Position = vec4(vertex.xy,0.,1.);
}